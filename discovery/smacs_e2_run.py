"""Budget-reserved acquisition and official pipeline execution for frozen SMACS E2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

E2_FREEZE = "19f2702294b680d2961045c55a508a6edcd157b4"
APPROVED_UTC = "2026-10-14T01:45:14Z"
CAP = 6_442_450_944
PRIOR = 226_670_400
RECEIPTS = Path("research_output/session_20261014")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def child_rss_kib(child_pid: int, proc: Path = Path("/proc")) -> int | None:
    """Resolve our direct child when procfs exposes a different PID namespace."""

    def status(path: Path) -> dict[str, str]:
        return dict(line.split(":", 1) for line in path.read_text().splitlines() if ":" in line)

    parent_pid = int(status(proc / "self/status")["Pid"])
    matches = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = status(entry / "status")
            namespace_ids = fields.get("NSpid", fields["Pid"]).split()
            if int(fields["PPid"]) == parent_pid and int(namespace_ids[-1]) == child_pid:
                if "VmRSS" in fields:
                    matches.append(int(fields["VmRSS"].split()[0]))
        except (OSError, KeyError, ValueError):
            continue
    return matches[0] if len(matches) == 1 else None


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def require_freeze(commit: str) -> None:
    if commit != E2_FREEZE:
        raise ValueError("wrong approved E2 freeze")
    name = "docs/frozen/E2_SMACS1043_BUDGET_DESIGN.md"
    frozen = subprocess.check_output(["git", "show", f"{commit}:{name}"])
    if frozen != Path(name).read_bytes():
        raise ValueError("frozen design changed")


def reserve(ledger: dict, product_bytes: int) -> None:
    if product_bytes <= 0 or ledger["reserved_total_bytes"] + product_bytes > CAP:
        raise ValueError("response reservation exceeds E2 cumulative cap")
    ledger["reserved_total_bytes"] += product_bytes


def acquire(args: argparse.Namespace) -> None:
    require_freeze(args.freeze_commit)
    if args.cap_bytes != CAP or args.prior_charge_bytes != PRIOR:
        raise ValueError("budget differs from approved freeze")
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError("existing acquisition ledger: reconcile before any retry")
    selector_path = RECEIPTS / "e2_selector.json"
    selector = json.loads(selector_path.read_text())
    if (
        selector.get("status") != "unchanged current selector"
        or selector.get("freeze_commit") != E2_FREEZE
    ):
        raise ValueError("fresh current-selector gate failed")
    raw = json.loads((RECEIPTS / "e_raw_downloads.json").read_text())["receipts"]
    refs = json.loads((RECEIPTS / "e_reference_heads.json").read_text())["products"]
    products = [
        {
            "name": r["product_id"],
            "url": r["requested_url"],
            "bytes": r["bytes"],
            "expected_sha256": r["sha256"],
            "kind": "raw",
        }
        for r in raw
    ] + [
        {
            "name": r["filename"],
            "url": r["requested_url"],
            "bytes": int(r["content_length"]),
            "kind": "reference",
        }
        for r in refs
    ]
    ledger = {
        "freeze_commit": E2_FREEZE,
        "approved_utc": APPROVED_UTC,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "cap_bytes": CAP,
        "prior_conservative_bytes": PRIOR,
        "reserved_total_bytes": PRIOR,
        "actual_new_body_bytes": 0,
        "products": [],
        "status": "acquiring",
        "context": "jwst_1596.pmap",
    }
    save(args.output, ledger)
    for p in products:
        destination = args.cache / p["name"]
        if destination.exists():
            raise FileExistsError("unledgered file requires reconciliation")
        reserve(ledger, p["bytes"])
        row = {**p, "reserved_bytes": p["bytes"], "body_bytes": 0, "status": "reserved"}
        ledger["products"].append(row)
        save(args.output, ledger)
        partial = destination.with_suffix(destination.suffix + ".partial")
        h = hashlib.sha256()
        try:
            # No retries; reservation remains charged even if the request fails.
            with urlopen(
                Request(p["url"], headers={"User-Agent": "jwst-frozen-e2/1"}), timeout=60
            ) as response:
                row["resolved_url"] = response.url
                row["http_status"] = response.status
                if response.status != 200 or int(response.headers["Content-Length"]) != p["bytes"]:
                    raise ValueError("body identity/length differs from frozen HEAD plan")
                with partial.open("xb") as stream:
                    while chunk := response.read(1024 * 1024):
                        row["body_bytes"] += len(chunk)
                        ledger["actual_new_body_bytes"] += len(chunk)
                        h.update(chunk)
                        if row["body_bytes"] > p["bytes"]:
                            raise ValueError("body exceeds reserved response length")
                        stream.write(chunk)
                        save(args.output, ledger)
                if row["body_bytes"] != p["bytes"]:
                    raise ValueError("truncated body")
                row["sha256"] = h.hexdigest()
                if p.get("expected_sha256") and row["sha256"] != p["expected_sha256"]:
                    raise ValueError("restored raw bytes differ from E1 pin")
                partial.replace(destination)
                row["status"] = "complete"
                row["completed_utc"] = datetime.now(timezone.utc).isoformat()
        except BaseException as exc:
            row["status"] = "failed"
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["partial_sha256"] = h.hexdigest()
            ledger["status"] = "blocked: acquisition failure"
            save(args.output, ledger)
            partial.unlink(missing_ok=True)
            raise
        save(args.output, ledger)
    ledger["status"] = "complete"
    save(args.output, ledger)


def reduce_worker(cache: Path, output: Path) -> None:
    """Network-disabled child: all reference bodies must have been ledgered."""
    import urllib.request

    output.mkdir(parents=True, exist_ok=True)
    real_open = urllib.request.urlopen
    network = {"freeze_commit": E2_FREEZE, "body_bytes": 0, "reads": []}
    prior_metadata = json.loads((RECEIPTS / "e2_selector.json").read_text())["metadata_body_bytes"]
    metadata_allowance = 30_000_000 - prior_metadata
    network_path = output / "metadata_network.json"

    class MetadataTap:
        def __init__(self, response, url):
            self.response = response
            self.url = url

        def __getattr__(self, name):
            return getattr(self.response, name)

        def read(self, size=-1):
            remaining = metadata_allowance - network["body_bytes"]
            maximum = remaining + 1 if size < 0 else min(size, remaining + 1)
            body = self.response.read(maximum)
            network["body_bytes"] += len(body)
            network["reads"].append(
                {"url": self.url, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            )
            save(network_path, network)
            if network["body_bytes"] > metadata_allowance:
                raise RuntimeError("metadata response cap exceeded")
            return body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.response.__exit__(*args)

    def metadata_only(url, *args, **kwargs):
        address = url.full_url if hasattr(url, "full_url") else str(url)
        if "jwst-crds.stsci.edu" not in address or "/references/" in address:
            raise RuntimeError("unmanifested pipeline data/reference request is forbidden")
        kwargs["timeout"] = min(kwargs.get("timeout", 25), 25)
        return MetadataTap(real_open(url, *args, **kwargs), address)

    urllib.request.urlopen = metadata_only
    os.environ["CRDS_MODE"] = "remote"
    os.environ["CRDS_CLIENT_RETRY_COUNT"] = "1"
    os.environ["CRDS_CLIENT_TIMEOUT_SECONDS"] = "25"
    os.environ["CRDS_PATH"] = "/workspace/scratch/337bba29e79a/e_smacs_crds"
    os.environ["CRDS_SERVER_URL"] = "https://jwst-crds.stsci.edu"
    from jwst.pipeline import Detector1Pipeline, Image2Pipeline

    refmap = json.loads((RECEIPTS / "e_crds_remote.json").read_text())["references"]
    output.mkdir(parents=True, exist_ok=True)
    receipt = {"freeze_commit": E2_FREEZE, "context": "jwst_1596.pmap", "exposures": []}
    save(output / "steps.json", receipt)
    for raw in sorted(cache.glob("*_uncal.fits")):
        row = {"raw": raw.name, "steps": {}, "started_utc": datetime.now(timezone.utc).isoformat()}
        receipt["exposures"].append(row)
        save(output / "steps.json", receipt)
        models = []
        try:
            value = str(raw)
            for cls in (Detector1Pipeline, Image2Pipeline):
                pipeline = cls(output_dir=str(output), save_results=True)
                for name in pipeline.step_defs:
                    step = getattr(pipeline, name)
                    for kind in step.reference_file_types:
                        selected = refmap.get(kind, "NOT FOUND n/a")
                        override = (
                            "N/A" if selected.startswith("NOT FOUND") else str(cache / selected)
                        )
                        setattr(step, "override_" + kind, override)
                row.setdefault("pipeline_parameters", {})[cls.__name__] = pipeline.get_pars()
                returned = pipeline.run(value)
                if isinstance(returned, list):
                    if len(returned) != 1:
                        raise ValueError("expected one science product per fixed exposure")
                    model = returned[0]
                else:
                    model = returned
                models.append(model)
                row["steps"][cls.__name__] = dict(model.meta.cal_step.instance)
                row["calibration_version"] = model.meta.calibration_software_version
                row["reference_context"] = model.meta.ref_file.crds.context_used
                save(output / "steps.json", receipt)
                value = model
            row["status"] = "pipeline completed; scientific gates not yet evaluated"
        except BaseException as exc:
            row["status"] = "blocked: pipeline error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            save(output / "steps.json", receipt)
            raise
        finally:
            for model in models:
                model.close()
        save(output / "steps.json", receipt)


def reduce(args: argparse.Namespace) -> None:
    require_freeze(args.freeze_commit)
    acquisition = json.loads((RECEIPTS / "e2_acquisition.json").read_text())
    if acquisition["status"] != "complete" or acquisition["reserved_total_bytes"] > CAP:
        raise ValueError("acquisition gate failed")
    verified = {row["name"]: row for row in acquisition["products"] if row["status"] == "complete"}
    expected = {
        row["filename"]
        for row in json.loads((RECEIPTS / "e_reference_heads.json").read_text())["products"]
    }
    expected.update(
        row["product_id"]
        for row in json.loads((RECEIPTS / "e_raw_downloads.json").read_text())["receipts"]
    )
    if set(verified) != expected:
        raise ValueError("final verified contributor/reference set differs from freeze")
    for name, row in verified.items():
        if digest(args.cache / name) != row["sha256"]:
            raise ValueError("acquired input hash changed")
    directory = args.cache / "pipeline"
    command = [
        sys.executable,
        "-m",
        "discovery.smacs_e2_run",
        "worker",
        "--cache",
        str(args.cache),
        "--output",
        str(directory),
        "--freeze-commit",
        E2_FREEZE,
    ]
    logpath = args.cache / "pipeline.log"
    with logpath.open("w") as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        maximum_kib = 0
        stop_reason = None
        while child.poll() is None:
            rss = child_rss_kib(child.pid)
            if rss is None and child.poll() is not None:
                break
            maximum_kib = max(maximum_kib, rss or 0)
            memory = Path("/proc/meminfo").read_text().splitlines()
            available = next(int(s.split()[1]) for s in memory if s.startswith("MemAvailable:"))
            fs = os.statvfs(args.cache)
            if (
                rss is None
                or rss > int(6.5 * 1024**2)
                or available < 1024**2
                or fs.f_bavail * fs.f_frsize < 2 * 1024**3
            ):
                stop_reason = (
                    "worker resource telemetry unavailable"
                    if rss is None
                    else "frozen physical resource stop"
                )
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                break
            time.sleep(1)
        code = child.wait()
    receipt = {
        "freeze_commit": E2_FREEZE,
        "returncode": code,
        "max_rss_kib": maximum_kib,
        "resource_stop": stop_reason,
        "log_sha256": digest(logpath),
        "scientific_gates_evaluated": False,
        "max_rss_scope": "Namespace-resolved child RSS sampled once per second; "
        "between-sample peaks remain unverified.",
        "resource_guard_verified": False,
    }
    if (directory / "steps.json").exists():
        receipt["pipeline"] = json.loads((directory / "steps.json").read_text())
    save(args.output, receipt)
    if code != 0:
        raise SystemExit(code or 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["acquire", "reduce", "worker"])
    parser.add_argument("--freeze-commit", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cap-bytes", type=int, default=CAP)
    parser.add_argument("--prior-charge-bytes", type=int, default=PRIOR)
    args = parser.parse_args()
    if args.mode == "acquire":
        acquire(args)
    elif args.mode == "reduce":
        reduce(args)
    else:
        require_freeze(args.freeze_commit)
        reduce_worker(args.cache, args.output)


if __name__ == "__main__":
    main()

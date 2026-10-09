"""Audit saved per-source trials without rerunning or inventing observations.

python -m discovery.validation_audit --output research_output/validation_audit.json \
    --report research_output/VALIDATION_AUDIT.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from discovery.validation_metrics import evaluate_external_validation, injection_metrics


def audit_injections(payload: dict[str, Any]) -> dict[str, Any]:
    """Recompute metrics from trials; saved aggregate percentages are not trusted."""
    injections = payload.get("injections")
    if not isinstance(injections, dict) or not injections:
        raise ValueError("report needs nonempty per-filter injections, not just summary rates")
    filters = {}
    for name, rows in sorted(injections.items()):
        if not isinstance(rows, list):
            raise ValueError("each filter needs a list of per-source outcomes")
        faint = [r for r in rows if r["half_light_radius_px"] == 0.0 and r["target_snr"] <= 8.0]
        filters[name] = {"overall": injection_metrics(rows),
                         "faint_point_sources": injection_metrics(faint),
                         "by_target_snr": {str(snr): injection_metrics([r for r in rows if r["target_snr"] == snr])
                                           for snr in sorted({r["target_snr"] for r in rows})}}
    return {"filters": filters, "independence_status": "unverified",
            "limits": ["These are committed synthetic injection trials, not independent real-source recovery.",
                       "Legacy trials do not record stable source, field, visit, generator and PSF provenance.",
                       "Wilson intervals assume independent Bernoulli trials. Shared images/PSFs and batch clustering may narrow them artificially.",
                       "No detector calibration, PSF mismatch or astrophysical systematics are included.",
                       "No new FITS processing or source observations were performed."]}


def _rate_text(rate: dict[str, Any]) -> str:
    if rate["estimate"] is None:
        return "not estimable (0 trials)"
    return (f"{rate['successes']}/{rate['trials']} = {100 * rate['estimate']:.1f}% "
            f"[{100 * rate['lower']:.1f}, {100 * rate['upper']:.1f}]%")


def render_report(audit: dict[str, Any]) -> str:
    lines = ["# Validation audit of committed injection outcomes", "",
             f"Input SHA-256: `{audit['input_sha256']}`", "",
             "Every rate below is recomputed from per-source outcomes. Brackets are",
             "95% Wilson binomial intervals conditional on these trials, not total scientific uncertainty.", "",
             "| Filter/sample | Detected / injected | Rejected / classified | Accepted / injected |",
             "| --- | --- | --- | --- |"]
    for name, groups in audit["filters"].items():
        for sample in ("overall", "faint_point_sources"):
            m = groups[sample]
            lines.append(f"| {name} {sample} | {_rate_text(m['detection_completeness'])} | "
                         f"{_rate_text(m['false_rejection_among_classified'])} | "
                         f"{_rate_text(m['end_to_end_completeness'])} |")
    lines += ["", "An observed zero rejection rate has a nonzero upper uncertainty bound.",
              "Passing the classifier is conditional on detection; it does not restore sources missed by the detector.",
              "Null classifier decisions remain unknown, never accepted by default.", "", "## Limits", ""]
    lines += [f"- {limit}" for limit in audit["limits"]]
    if "external_validation" in audit:
        result = audit["external_validation"]
        lines += ["", "## Supplied external validation", "", result["claim"], "",
                  f"Provenance independence: **{result['independence']['status']}**.",
                  f"AUC: {result['roc_auc']['value']} ({result['roc_auc']['status']})."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("research_output/injection_recovery.json"))
    parser.add_argument("--external-validation", type=Path, help="Frozen model predictions plus split provenance")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = audit_injections(json.loads(raw))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    if args.external_validation:
        result["external_validation"] = evaluate_external_validation(json.loads(args.external_validation.read_bytes()))
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_report(result), encoding="utf-8")
    if not args.output and not args.report:
        print(encoded)
    if "external_validation" in result and not result["external_validation"]["independence"]["independent_validation_permitted"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

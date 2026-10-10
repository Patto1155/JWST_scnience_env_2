"""Verify the pilot's default atomic families against the complete pinned archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import time
from pathlib import Path

from data_pipeline.cloudy_inputs import verify

MEMBERS = (
    "data/stout/masterlist/Stout.ini",
    "data/chianti/masterlist/CloudyChianti.ini",
    "data/chianti/VERSION",
    "data/h_iso_recomb.dat",
    "source/init_defaults_preparse.cpp",
    "source/species.cpp",
    "source/iso_create.cpp",
    "source/iso_solve.cpp",
    "source/iso_radiative_recomb.cpp",
    "source/hydrocollid.cpp",
)
FAMILIES = {
    "NIV": ("n_4", "Stout"),
    "NIII": ("n_3", "CHIANTI"),
    "CIII": ("c_3", "Stout"),
    "CIV": ("c_4", "CHIANTI"),
    "OIII": ("o_3", "Stout"),
    "NV": ("n_5", "Stout"),
    "CII": ("c_2", "Stout"),
}


def active_species(text: str) -> set[str]:
    return {
        line.split("#", 1)[0].split()[0]
        for line in text.splitlines()
        if re.match(r"^[a-z]+_\d+(\s|$)", line.split("#", 1)[0].strip())
    }


def audit(directory: Path) -> dict:
    started = time.monotonic()
    archive_receipt = verify(directory / "c23.01.tar.gz")
    wanted = {"c23.01/" + name for name in MEMBERS}
    verified = []
    with tarfile.open(directory / "c23.01.tar.gz") as archive:
        for member in archive:
            if member.name not in wanted:
                continue
            payload = archive.extractfile(member).read()
            if payload != (directory / member.name).read_bytes():
                raise ValueError("actual atomic-selection input differs from pinned archive")
            verified.append(
                {
                    "member": member.name,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            wanted.remove(member.name)
    if wanted:
        raise ValueError("required atomic-selection member missing from complete archive")
    source = directory / "c23.01"
    defaults = (source / "source/init_defaults_preparse.cpp").read_text()
    for required in (
        "atmdat.lgChiantiOn = true;",
        "atmdat.lgStoutOn = true;",
        'strcpy(atmdat.chCloudyChiantiFile, "CloudyChianti.ini");',
        'strcpy(atmdat.chStoutFile, "Stout.ini");',
    ):
        if required not in defaults:
            raise ValueError("unexpected release default atomic-family selection")
    masters = {
        "Stout": active_species((source / MEMBERS[0]).read_text()),
        "CHIANTI": active_species((source / MEMBERS[1]).read_text()),
    }
    selections = {}
    for group, (species, family) in FAMILIES.items():
        present = [name for name, entries in masters.items() if species in entries]
        if present != [family]:
            raise ValueError("default atomic species missing or selected by two families")
        selections[group] = {"species": species, "database": family}
    runtime = time.monotonic() - started
    if runtime > 60:
        raise TimeoutError("bounded atomic provenance audit exceeded60s")
    return {
        "schema_version": 1,
        "archive": archive_receipt,
        "default_atomic_selections": selections,
        "CHIANTI_version": (source / "data/chianti/VERSION").read_text().strip(),
        "HeII": {
            "family": "Internal H-like isoelectronic solver, including He+",
            "recombination_table": "data/h_iso_recomb.dat",
            "scope": "Whole archive pins all other rates; selected source pins document the solver",
        },
        "members_verified_against_archive_and_actual_cache": verified,
        "runtime_seconds": runtime,
        "scope": (
            "Default families apply to the declared decks with no database override. "
            "This establishes versioned provenance, not empirical atomic-rate accuracy."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloudy-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.cloudy_directory), indent=2) + "\n")


if __name__ == "__main__":
    main()

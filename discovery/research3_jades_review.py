"""Portable operator CLI for independent JADES catalogue and spectrum reviews.

This module does not import the candidate-fitting modules and never inspects
GOODS-N catalogue outcome rows. These diagnostics do not certify discoveries.
"""

from __future__ import annotations

import argparse

from discovery import research3_jades_catalog_review, research3_jades_spectrum_review


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["catalogue", "spectrum"])
    args, remainder = parser.parse_known_args(argv)
    if args.mode == "catalogue":
        research3_jades_catalog_review.main(remainder)
    else:
        research3_jades_spectrum_review.main(remainder)


if __name__ == "__main__":
    main()

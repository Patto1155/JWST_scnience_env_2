# Reproducible continuation protocol

Baseline: master `8875fe1`, including merged PRs #1–#13. The authoritative
starting claims are in `TAKEOVER_STATUS.md`; older reports remain provenance.

## Ownership and dependencies

| Role | Owns | Requires |
|---|---|---|
| Astrometry | Original-image receipts, frame residuals, repeat coverage | Public MAST products and external reference coordinates |
| Photometry | Fresh proposal catalog, calibrated dropout audit, joint usable area | Verified images and astrometric frame |
| Real-source validation | Frozen classifier, stellar and galaxy denominators, grouped controls | Independently labelled sources and covered imaging |
| PSF/noise | Encircled energy, differential colors, empirical blank-aperture errors | Pinned PSF templates; real images for sky-noise claims |
| Spectroscopy | Quality masks, bin-integrated line models, covariance and extraction tests | Verified MoM-z14 spectrum and resolution calibration |
| Enrichment | Time budgets, yield dilution/retention, discriminating predictions | Primary numerical yields; spectral constraints |
| Literature/data | Versioned primary sources and missing public products | Acquisition caps and scientific questions |
| Adversarial review | Independent reproduction, counterexamples, interpretation audit | Frozen outputs and exact code revisions |

The first six roles run concurrently; the last two rotate in as slots open.
Trusted coding agents work in separate branches/worktrees. Focused changes are
tested and merged before later experiments depend on them. Runtime LLM workers
retain their registered-tool restrictions; this workflow does not loosen them.

## Evidence contract

* Observations: measured values from identity-verified actual products, with units,
  quality masks, denominators and checksums. Processed public data include the
  upstream reduction choices; a checksum does not certify their validity.
* Assumptions: PSF family, resolution, covariance, extraction, cosmology, density,
  ionization, yields, retention and formation epoch are explicit inputs.
* Inferences: retain conditional uncertainty and sensitivity across assumptions.
  A line ratio is not an elemental abundance; a cosmic age is not a galaxy age.
* Controls: modeled PSFs and synthetic calibration trials are labelled as such.
  Their success does not establish observed-sky recovery or independent truth.
* Speculation: new-physics explanations enter only with quantitative predictions
  and a measured selection function. A saved proposal is not a discovery.

Missing images produce an explicit blocked status. Zero eligible reference
objects mean not estimable, never 0% recovery. Preserve historical catalogs and
write fresh reruns under separate paths. Keep repeated observations of one object
together; report trials, detections, retention and final selection separately.

## Environment and bounded acquisition

Python 3.12. A dependency snapshot from the passing baseline is stored in
`requirements-research.lock`. Reproduce with:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-research.lock
.venv/bin/python scripts/quality_gate.py
```

The continuation acquisition budgets are 1.5 GiB for selected original GOODS-S/SMACS
imaging and 600 MiB for the real-star catalogue/images. Verify exact public URLs,
byte counts, SHA256 and data identity. Raw large images stay outside git; commit
receipts, acquisition instructions, compact derived results and code. Public
access and published scientific acknowledgements remain part of provenance.

As executed reports are merged, their documented CLIs and pinned inputs become
the reproducibility entry points. The dependency lock records an environment,
not a promise of bitwise output equivalence across CPU/BLAS implementations.

The executed continuation additionally bounds each modeled PSF download at
5 MiB, follow-up pilot data at 100 MiB, and the nine-exposure native MoM batch
at 600 MiB (64 MiB per file). Its aggregate includes the exposure acquired in
the pilot and does not count that shared file as an independent observation.
Inventories version the exact products; current status and executed reports
record actual bytes and retained methodological dependencies.

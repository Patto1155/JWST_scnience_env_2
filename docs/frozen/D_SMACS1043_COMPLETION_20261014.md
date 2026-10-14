# SMACS 1043 completion design — 2026-10-14

This bounded completion preserves E2 scientific gates and recognizes the already
observed failures: three of four structured-light rank gates and the separate
source association gate failed. Injection cannot override those failures. This
is a reproducibility/prerequisite assessment, not blind confirmation.

Inputs: immutable E2 design (19f2702294b680d2961045c55a508a6edcd157b4),
`e2_geometry.json`, two E2 compact calibrated FITS products, and existing
`e2_photometry.json`. No GOODS-N or unrelated target data are authorized.

## Injection grid frozen before new array access

Flux levels remain +1000, +1500, and -1000 nJy of fixed-aperture flux.
Injection coordinates are exactly every retained E2 control ring coordinate
(279 entries in the committed geometry), offsets (east,north)=(0,0) arcsec
relative to each coordinate, one trial at each flux in each of the two images:
279 × 3 × 2 = 1674 planned image trials. No favorable locations are selected.
Use copies, retain signed flux, and use each of the four E2 operators. Positive
levels require ≥90% detection/centroid recovery and median recovered/input
[0.8,1.2]; negative injections permit ≤5% false positives. The original
centroid, empirical-noise, null and multiplicity gates remain binding.

Before trials, independently establish that the E2 metadata-selected nearest
covered eligible catalogue core is an unsaturated point source and that a
measured same-field PSF passes the original held-out reduced-chi2 ≤2 gate.
Neither a bright isolated core, its own self-fitted empirical image, an imported
JADES PSF, nor absent saturation metadata establishes that prerequisite.
Existing compact products preserve SCI/ERR/WHT and WCS but omit native DQ and
provide no certified point-source identity or independent PSF residual control.
If these requirements cannot be established, record the precise blocker and do
not run artificial injections as if they supplied sky calibration. No new PSF
selection threshold or calibration reference is introduced.

## Replay and other epoch

After coordinator clearance of the session amendments, replay the four original
operators on compact products and compare target fluxes (absolute tolerance
1e-5 nJy), rank p and decisions to existing E2 receipts. No full-image
astrometric reconstruction is claimed from these compact products.

Retry the recorded metadata-only MAST filtered-position request once with a
30-second timeout and at most 5,000,000 response bytes. Account all response
bytes, including failures, separately from science bodies. The earliest public
complete calibrated F444W epoch ≥1 day from the original midpoints whose
footprint covers the fixed 1-arcsec target disk is eligible. Incomplete or
failed metadata cannot establish absence of an epoch. No download without
verified identity, coverage, midpoint, full length, sufficient disk (>5GB),
and cumulative E2 reservation within 6,442,450,944 bytes. Current carried
reservation 5,826,074,168 leaves 616,376,776 bytes. No reset on deletion.

Outputs: docs/SMACS1043_COMPLETION.md and
research_output/calibrated_20261014/d_* receipts. Record freeze commit and first
new array access. Focused acceptance: original four SMACS tests plus actual
compact replay. No state-file edits, raw commits or grade promotions. List all
not-run/unverified work. No physical rejection follows from a missing PSF or
failed archive access.

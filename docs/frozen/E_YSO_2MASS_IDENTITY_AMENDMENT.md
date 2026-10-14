# E metadata-only catalogue association amendment, 2026-10-14

Before any new official 2MASS query, resolve the six selected South YSOs whose
SIMBAD allfluxes K cell is empty against the official IRSA 2MASS Point Source
Catalogue `fp_psc`. An empty SIMBAD cell is not proof of absent 2MASS photometry.

Use a fixed1arcsec cone around the retained published coordinates. Require one
unique counterpart; no nearest-choice selection from ambiguous counterparts.
Multiple/zero matches are unresolved association under this bounded screen,
not proof that no infrared counterpart exists. Retain identities, angular
separation, K magnitude/quality/errors, metadata receipts and exact query. No
science pixels or variability outcomes. Do not substitute targets, expand
radius or change K-matched control, UTC-day, channel-count or5target/8visit gates.
This is a catalogue identity resolution clarification, not a new hypothesis.

If any counterpart has valid finite K, perform the original frozen control
screen without changing its cuts. Other same-field source coverage remains
unknown; no science products or coarse WCS range bodies are permitted here.
Budget remains30MB direct metadata, including earlier receipts; >5GB disk floor.

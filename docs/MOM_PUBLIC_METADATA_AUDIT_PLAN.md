# Bounded public MoM spectral/calibration inventory audit

Predeclared 2026-10-10, before the new remote queries. Base: live master
`cf2f10d8521dbadb88c78a21580cb5257b234866`.

Question: do public metadata identify additional observations of the actual
MoM source or updated applicable calibration inputs beyond the pinned nine
CAL/RATE exposures and recovered author PIXTAB?

The source identity is the pinned coordinate (150.0933255, 2.2731627 degrees),
NIRSpec program 5224, source 277193. Existing products/context are the
comparison baseline, not evidence that all public archives are exhausted.

Competing outcomes: an additional public on-source spectral exposure or a
different applicable calibration reference may warrant a separate reduction;
unchanged release/contributor metadata would leave measured source-specific
wavelength/LSF information unresolved. Nearby spectra or planned shutters do
not establish a public on-source observation. A newer CRDS context alone does
not establish a changed applicable reference or empirical source calibration.

Budget: at most 12 remote catalog/query endpoints, at most 1,048,576 response
bytes total, and five minutes of querying. Metadata only: no full FITS data.
Use bounded reads and record each accepted response's URL, status, bytes and
SHA256, plus observed failures. Query author extraction and shutter releases,
MAST cone/program metadata, and CRDS public reference provenance as accessible.
Stop after a clear contributor/coverage inventory or documented access errors;
do not interpret access errors or unqueried endpoints as nonexistent data.

Validation: compare exact contributor names/coordinates against pinned CAL and
RATE manifests, inspect cached current CAL reference header identities, and
independently verify response hashes, endpoint counts and byte arithmetic.
Inventory results are archive work; new observing proposals and unavailable
author inputs remain separate external dependencies. No author contact.

# Rectified CAPERS source has no UV coordinates

The predeclared single-product pilotc6b864b stops with zero2.15–3.20um
wavelength pixels in the actual sourceS2D, before any data-quality selection.
This rejects the explanation that the official sourceX1D UV gap exists solely
in its one-dimensional extraction mask. It does not establish zero UV flux,
an upper limit, or absence of information in every lower-stage detector product.

One GET acquired1,353,600newbytes in5.754seconds; no retry, failure, HEAD or
restoration occurred. SHA256 is
`e740bc3a803ecb3d24a19485c1674cf809faf948a5dd8c84c7575329db9de9cb`.
The exact PUBLIC source-product URI/catalog association and response headers
are pinned in `data_sources/capers_s2d/receipt.json`. This is a separate
allocation, preserving the preceding companion audit's eight-endpoint cap.
Transport/header overhead is unmeasured. No other data or full CAL/RATE inputs
were downloaded, and no flux fitting or extraction was performed.

The actual SCI header verifies source102896, slit139, sourcePOINT and coordinates
(150.0933178,2.2731591). Primary provenance is MULTIPLE detectors,
pipeline3.0.0/context1584 and the exact same spec3 association as the acquired
sourceX1D. HDRTAB independently lists36science contributors:18NRS1+18NRS2,
matching every science member of the actual association JSON. This is a real
source-specific combined product rather than a field footprint inference.

| Check | Actual result |
| --- | ---: |
| SCI/ERR/WAVELENGTH/WHT shape |31×277 |
| Finite wavelength coordinates |8587 |
| Finite SCI and ERR |7049 |
| Positive ERR/WHT and nonzero contributor-context support |7049 |
| UV wavelength coordinates before quality cuts |0 |
| UV supported pixels before DQ |0 |
| DQ array supplied |No |
| UV support after supplied DQ |Unavailable |

There is no DQ extension, so missing flags are never replaced with zeros or
reported as validated. Zero UV coordinates means any subsequent flag subset
also has zero UV support. CON is a two-plane signed bitmask; nonzero values,
including negative values with the high contributor bit set, provide support.
Context counts do not establish independent exposure likelihoods.

SCI and ERR explicitly use MJy. WAVELENGTH has no BUNIT keyword, but the
embedded ASDF WCS spectral frame explicitly specifies um and maps its wavelength
array to FITS:WAVELENGTH,1. Every spatial row matches the independently
unit-tagged sourceX1D wavelength grid within1e-6um. The combined grid has the
same1.84305346–3.89722419um gap and no UV coordinates. The ASDF metadata is
inspected as text; no fetched code is executed or serialized objects evaluated.
Pipeline source calibration, resampling, extraction and covariance remain
assumptions, and the actualwavecorr0004 reference remains DUMMY.

This completes the bounded metadata/compact-product acquisition track. A
subsequent raw source-geometry audit ranks below the existing native MoM
measurement/covariance work: it could independently inspect MSA shutter/detector
trace placement and pipeline wavelength assignment to decide whether raw
CAPERS UV support was omitted before rectification. The present source-specific
X1D and S2D provide no usable UV data. New observing time should be distinguished
from that remaining accessible lower-stage geometry question; neither detector
availability nor the absence of rectified samples alone proves it necessary.

Reproduce without network:

```bash
python -m data_pipeline.capers_s2d_coverage --output /tmp/capers-s2d-coverage.json
python -m pytest tests/test_capers_s2d_coverage.py \
  tests/test_capers_companion_coverage.py tests/test_capers_pixtab_coverage.py \
  tests/test_mom_compact_followup.py tests/test_mom_public_metadata.py
```

Twelve focused tests and strict Ruff E/F/I pass. Tests include a negative context
bit, negative SCI values, explicit missing DQ and actual source/pagination/
coverage invariants. Independent actual-input spectroscopy validation must
confirm whole-file identity, source/contributor provenance and zero-coordinate
coverage before merge. No scientific abundance, identity or redshift changed.

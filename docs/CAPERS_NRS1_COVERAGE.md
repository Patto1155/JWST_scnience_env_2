# Official combined-source CAPERS X1D has no UV samples

The predeclared companion gate2e8478f completed all seven pages of the exact
source-association inventory for MASTobsid266381037, reusing hash-verified
page1. The630rows represent553uniqueproductfilenames; repeated pool/association
references are deduplicated, not treated as independent products. Every row's
parent_obsid matches266381037. Source-specific PUBLIC X1D and spec3 association
products were selected by exact metadata, not guessed filenames.

The eight new endpoints acquired1,219,486bytes:318,936pagination metadata,
13,510association JSON and887,040sourceX1D. No retries, failures or restoration
occurred. The last endpoint completed161.986seconds after the first request;
active query durations sum67.184seconds. Headers/transport overhead are not
part of payload accounting. Receipts and actual products are versioned under
`data_sources/capers_companion`; the prior eight-endpoint allocation remains
unchanged. No full CAL/RATE or flux fitting was performed.

The sourceX1D SHA256 is
`06a925cf57715f392091679e548acb5a8a2c5248e79a241e56be8d3169e240e2`.
Its actual EXTRACT1D header verifies source102896, slit139 and exactly
(150.0933178,2.2731591), source typePOINT and detectorMULTIPLE. Primary
provenance is pipeline3.0.0/context1584, with ASNTABLE exactly matching the
acquired spec3 association. That association supplies36distinctscience members
(18NRS1,18NRS2) on the same18exposure roots as the author release, plus8target
acquisition members that are not science contributors. NRS1 is available;
the author NRS2-only intermediate was not an exhaustive detector inventory.

The official spectrum has277finite strictly increasing wavelength coordinates,
249samples with finite flux, positive finite error, positive NPIXELS and
neither DO_NOT_USE nor SATURATED. Wavelength/flux/error units are um/Jy/Jy.
Its endpoints0.551698–5.372151um do not imply continuous spectral coverage:
the largest adjacent gap runs1.84305346–3.89722419um. There are zero wavelength
samples and zero usable samples in2.15–3.20um before/after flags. This rejects
usable UV coverage in this exact compact sourceX1D, not zero UV flux.
The actual R_WAVCOR is stillwavecorr0004.asdf, previously whole-file verified
with DUMMY pedigree; a newer official reduction does not establish empirical
source wavelength calibration.

The combined X1D does not label each wavelength by detector/contributor.
Its pipeline extraction/resampling and covariance have not been reproduced.
The public sourceS2D is1,353,600bytes and remained unqueried at this gate's
endpoint/aggregate stop. It is an accessible dependency for distinguishing
an extraction omission from absent rectified source coverage. Lower-stage
source geometry likewise remains accessible. New UV observing time is not
declared necessary from these X1D endpoints or field products alone.

Reproduce without network:

```bash
python -m data_pipeline.capers_companion_coverage \
  --output /tmp/capers-companion-coverage.json
python -m pytest tests/test_capers_companion_coverage.py
```

The two tests cover signed-flux usability and frozen actual-input/pagination
invariants. Strict Ruff E/F/I passes. Independent spectroscopy validation of
whole-file identity, source/association provenance, units and gap/UV counts is
required before merge; no line detection, abundance, redshift or identity claim
has been made.

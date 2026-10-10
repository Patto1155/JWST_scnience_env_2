# Independent official CAPERS source X1D/S2D coverage review

Spectroscopy specialist independently inspected the actual frozen companion `a768eb3` and rectified source `db0e170` inputs. The separate oracle calls none of the author's analysis functions. It verifies all retained acquisition-response sizes and SHA256 hashes, exact source102896 atRA150.0933178/Dec2.2731591 with POINT type, both products' pipeline3.0.0/CRDS1584/MULTIPLE provenance and identical source ASNTABLE. The association has44 members, including36 science members and8 target-acquisition members. The actual S2D HDRTAB contains exactly the36 science filenames,18 from each detector. This validates the source association and source products, rather than inferring coverage from a field or mosaic footprint.

The X1D has277 wavelength rows,249 usable rows, explicit micron/Jy/Jy units and zero2.15–3.2um coordinates before quality cuts. Its largest coordinate gap is1.84305346–3.89722419um. The S2D supplies31×277 SCI/ERR/WAVELENGTH/WHT arrays and two signed context planes. Its8,587 wavelength pixels are finite; zero lie in2.15–3.2um before any science, error or flag selection. Exactly7,049 pixels have finite science/error and positive error/weight with nonzero contributor context. Context is a signed bitmask, so negative values are valid contributors. No DQ HDU is supplied: the review records unavailable post-DQ validation as null, never substitutes zero flags.

The WAVELENGTH HDU has no BUNIT. Independent inspection of the embedded ASDF spectral frame explicitly finds wavelength axes with micron units and the model wavelength array mapped to `fits:WAVELENGTH,1`. All row values exactly match the X1D grid after conversion to the stored S2D float32 precision; the original double-grid discrepancy is at most8.89e-16um. S2D SCI and ERR units are MJy, and this coverage review performs no flux conversion or fit. Three independent invariant tests check signed contexts, absent-DQ reporting and coordinate counts before selection; seven focused tests and Ruff pass. The actual-file oracle passes and its JSON records hashes and every pixel count.

The data reject an explanation that the UV gap occurs solely through the official X1D extraction or quality mask: it already exists in the rectified source coordinates. They establish no absence across all raw detector pixels, zero source UV flux, UV upper limit, counterpart identity, calibrated LSF or need for new observing time. Lower-stage trace geometry and upstream pipeline wavelength/selection remain a distinct accessible archive investigation. Shared contributors, resampling and diagonal product errors do not provide an independent exposure likelihood. No native nitrogen constraint changes.

Reproduce without downloading inputs:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_capers_source_review
python -m pytest -q tests/test_capers_source_review.py \
  tests/test_capers_companion_coverage.py tests/test_capers_s2d_coverage.py
```

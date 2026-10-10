# CAPERS PIXTAB contains no UV rows

The predeclared coverage gate8286753 stops this UV reduction track: the actual
CAPERS PIXTAB contains zero rows in2.15–3.20um, both before and after any
usability cuts. Missing coverage is not zero flux or a nitrogen upper limit.

The single GET acquired4,475,520newbytes in6.240seconds, with no HEAD, retry,
failure or restoration. Whole SHA256 is
`2c0d315274d0d0c74252f6d584e80636ae49e3a1361c0976216a366e8dbe6430`.
Whole-file MD5 matches the earlier single-part public ETag
`3740b9e9ddecfe9a8ef5cd559c56ea3f`. URLs/status/headers and byte accounting
are frozen in `data_sources/capers_coverage/receipt.json`; this allocation is
separate from prior compact/reference receipts. Transport/header overhead is
unmeasured. No additional products or full CAL/RATE inputs were acquired.

The FITS contains only PRIMARY and PIXTAB, with46,519rows and the established
12fields. Every field is finite. Wavelengths span3.94087652–5.49972968um;
pathloss spans0.609258–0.625487 and is positive throughout. Profiles have
29,275negative and17,244positive rows, none zero; signed rows are retained.
The frozen usability definition selects17,538rows using finite fields,
positive variance/pathloss/dwave/exptime, nonzero profile and -3≤yslit≤3.
It uses neither positive measured flux nor positive profile as a selection.

| Nominal group | PIXTAB rows | Usable rows | UV rows |
| --- | ---: | ---: | ---: |
| 03 | 7752 | 2923 | 0 |
| 05 | 7750 | 2922 | 0 |
| 07 | 7759 | 2926 | 0 |
| 09 | 7753 | 2926 | 0 |
| 11 | 7753 | 2922 | 0 |
| 13 | 7752 | 2919 | 0 |

Indices are exactly0–17. PIXTAB VERSION/profile/pathloss/extraction-range
settings match the hash-verified sibling SPEC; XPOS and each indexed exposure
duration match its ordered18SLITS entries. That sibling explicitly supplies
the18disjointNRS2contributors. PIXTAB itself carries no filenames or raw
detector coordinates: repeated XPOS/duration settings cannot independently
prove unique group identity. The group association is the pinned sibling's
ordering contract, and the zero UV count does not depend on that association.

Distinct groups also do not supply six independent author coadds. Exact shared
stored sky-value intersections are2584between exposure0/3 and2582between0/6,
witnessing cross-group reuse. The full18×18 matrix is recorded; it is not a
covariance estimate, detector-coordinate mapping or held-out exposure operator.
No spectrum was extracted or fitted in this experiment. The analysis runtime
was0.623seconds, inside the declared60second computation pilot.

The public author NRS2 intermediate is now checked directly. Possible NRS1
companion extraction/source-slit coverage remains unqueried and is not claimed
absent. This is a separate accessible archive question requiring its own
geometry/identity gate, not grounds to download18fullproducts speculatively.

Reproduce or restore the precise pinned input when scratch caches are absent:

```bash
python -m data_pipeline.capers_pixtab_coverage \
  --pixtab /tmp/capers_pixtab.fits --acquire \
  --output /tmp/capers-pixtab-coverage.json
python -m pytest tests/test_capers_pixtab_coverage.py \
  tests/test_mom_compact_followup.py tests/test_mom_public_metadata.py
```

Omit `--acquire` to replay a verified existing input. Restoration downloads
the same4,475,520-byte pin and must be accounted separately in future runs.
Eight focused tests and strict Ruff E/F/I pass. Independent spectroscopy
review47712c5 verifies the actual file SHA/MD5, schema, finite fields,
indices, signed profiles, positive pathloss and zero UV coverage without using
this author module. This result rejects the proposed hidden-UV-rows mechanism
for this released PIXTAB; no elemental abundance, identity or redshift changed.

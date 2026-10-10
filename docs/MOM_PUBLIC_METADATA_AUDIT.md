# Public MoM metadata inventory

The predeclared audit (`630351b`, MOM_PUBLIC_METADATA_AUDIT_PLAN.md) stopped at
12 endpoints and 470,251 response bytes, with 100.32 seconds of summed active
query durations. The receipt's 100.87-second clock accumulates the two query
phases and excludes the intervening analysis gap; it is not a continuous wall
clock or a sum of active durations. No full FITS or paid resources were acquired.
Accepted responses, URLs,
request payloads, status codes and SHA256 are frozen in
`data_sources/public_metadata/receipt.json`. The capped 262,144-byte CRDS
homepage is explicitly incomplete; its observed entries remain inspectable.

All nine cached original CAL files were rehashed against their pinned
inventory (464,135,040 existing bytes read locally, zero restoration/download).
Each contains source 277193 at (150.0933255, 2.2731627), EXTENDED, PRISM/CLEAR,
pipeline 2.0.1 / jwst_1535.pmap and wavecorr0004.asdf. Their exposure names
match the nine RATE manifest identities. This round does not independently
rehash the RATE pixels; those were validated in the earlier RATE review.

The author extraction and shutter responses are byte-identical to the prior
frozen public release queries. There is no newly indexed author version in
this coordinate query. The other released extraction, CAPERS6368/source102896,
lies 0.03058 arcsec from MoM and has source-shutter metadata at that position,
not merely a remote field footprint. Its exposure roots are disjoint from
MoM's nine: 18 CAPERS exposures totaling 17,069.004 seconds. MAST independently
returns an executed PUBLIC source-level record
`jw06368-o007_s000102896_nirspec_clear-prism` (obsid266381037, MJD60815.04–60815.30),
after MoM's MJD60781.13–60781.36. This is an accessible independent archive
lead, not an established alternative source identity. Its existing released
extraction covers 3.938–5.502 µm, outside the nitrogen UV features at z14.44,
and the grade1 z6.13832 catalog fit is not a verified astrophysical redshift.

The MAST position inventory is fully paginated (35 rows): six timed records
include the MoM/CAPERS source entries, another nearby source/background and
NIRCam grism footprints from programs6434/5893. Grism footprint coverage does
not establish an extracted spectrum of MoM. The other 29 records have null
times and programs10361/11892; their PUBLIC label does not establish executed
observations. Program5224 and product inventories were queried with page1 only
(883 program rows, 360 MoM product rows, 630 CAPERS product rows total). Their
partial returned samples prove public CAL/RATE entries, not an exhaustive
inventory or applicability of every same-association product to this slit.

CRDS1535.pmap selects NIRSpec0432.imap. The public latest homepage advertises
context1596 and a 3.0.0 build context1584. Five relevant rmap names agree
between the frozen1535 imap and observed latest-page entries: disperser0028,
pathloss0011, photom0013, wavecorr0005 and wavelengthrange0024. Matching names
alone do not prove identical selected references. The actual applicable
wavecorr0005 selector was not queried before the endpoint stop; the retrieved
older0004.rmap is clearly labeled and is not substituted for it. The public
metadata of the actual CAL reference wavecorr0004.asdf confirms DUMMY pedigree
and an internal0002 filename; this remains a sensitivity model.

The only HTTP failure was `/context_table/` returning404. This is an endpoint
failure, not absence of contexts; other public CRDS pages succeeded. Remaining
accessible work is exact current wavecorr selector evaluation, compact CAPERS
pixels/settings and coverage validation, and relevant product pagination.
New observing time and empirical source-specific wavelength/LSF information
remain separate from these accessible archive tasks. No abundance, identity,
redshift or spectral measurement changed in this metadata audit.

Reproduce without network:

```bash
python -m data_pipeline.mom_public_metadata --output /tmp/mom-public-metadata.json
python -m pytest tests/test_mom_public_metadata.py
```

Three tests pass, including independent angular geometry and deliberate receipt
corruption. Strict Ruff E/F/I passes for the module and tests. Independent review
must validate the accepted hashes, arithmetic, contributor geometry, public
status and incomplete-pagination limitations before merge.

# Exact wavecorr applicability and compact CAPERS spectrum

The predeclared pilot4316293 completed at seven endpoints, 718,228 accepted
response bytes and 52.873 seconds from first request to last endpoint. New
selected bytes are 701,775; 16,453 bytes separately restore the previously
pinned wavecorr reference. HEAD payloads are zero; no retries or failed requests
occurred. HTTP headers/transport overhead are not included in payload accounting.
Raw receipts, exact queries and whole-file SHA256 are in
`data_sources/compact_followup/receipt.json`. No full CAL/RATE was downloaded.

Context1535.pmap selects NIRSpec0432.imap; latest1596.pmap selects0444.imap.
Both explicitly select wavecorr0005.rmap. For NRS_MSASPEC and the actual MoM
observation2025-04-14 (MJD60781.1628), its UseAfter2015-11-01 branch selects
`jwst_nirspec_wavecorr_0004.asdf`. The restored whole file is16,453bytes,
SHA256 `869d4279137b1c7dea5e8bb4b4980d72fd0aa8423c87814050bfa710cd2b58f3`,
identical to the established pin. Its ASDF metadata states DUMMY pedigree,
internal filename0002, ESA origin and a simple toy MOS wavelength model.
The0005 mapping revision changes the N/A branch relative to0004; it does not
replace MoM's selected MOS reference. No source-specific empirical wavelength
or instrumental resolution calibration was gained. No existing CAL wavelength
array was modified or corrected again.

The compact public CAPERS spectrum is694,080bytes, SHA256
`170200ad6d1ba556ec1ee83c5427bc7fa0cd643de024d2697953c164d4be9e1b`.
Its actual SLITS table verifies18 NRS2 contributors from program6368/source102896,
at (150.0933178,2.2731591), totaling17,069.004seconds. Their six exposure/nod
groups match all18 source-shutter catalog roots and are disjoint from the nine
MoM roots. The position lies0.03058arcsec from MoM; source classification or
astrophysical sameness does not follow from that coincidence.

The author release has473 wavelength bins,195 with finite flux and positive
finite error and positive npix. Their range is3.93798944–5.50183332um. Columns
explicitly use um/uJy/uJy for wavelength/flux/error. The extraction is
msaexp0.9.5.dev8+ge2b237b, old CAL0.1.dev8704+g9b678d4/CRDS1298, ivm,
WITHPATH=True, PROFCEN0.0009999874, PROFSIG0.6978526782 and YMIN/YMAX=-3/+3.
This is an independent author-release extraction, not a current raw-pixel
reduction. Its diagonal errors do not supply a full covariance or independent
nod likelihoods. Shared calibration assumptions can correlate separate programs.

At z14.44 the tested UV nitrogen/carbon/He/O groups are outside that interval;
these pixels cannot directly update native nitrogen constraints. At the weak
catalog z6.13832, Halpha/NII/SII line-family wavelengths lie within the interval.
These are conditional observation predictions, not detections or a new linefit;
spectroscopy independently validates this spectrum before any likelihood use.
The grade1 catalog redshift remains unestablished. A separate predeclared fit
would need an adequate extraction/noise/attenuation contract before an absence
or presence of those lines could discriminate model families.

The public CAPERS PIXTAB HEAD succeeds and advertises4,475,520bytes. It exceeds
the two-MiB compact-input allocation and was not fetched. It is accessible
archive work requiring a revised bounded allocation, not an external public
access blocker. Lower-stage calibration or published-analysis reproduction
would need further detector/trace/covariance information; no such reproduction
is claimed here.

Reproduce the verified selection and coverage inventory without network:

```bash
python -m data_pipeline.mom_compact_followup --output /tmp/mom-compact-followup.json
python -m pytest tests/test_mom_public_metadata.py tests/test_mom_compact_followup.py
```

Six tests and strict Ruff E/F/I pass, including independent selector date/mode
oracles and rejection of executable/ambiguous selectors. Fetched mapping text
is parsed through AST and never executed. Independent reviewers must validate
whole-file identities, applicable selection and actual compact spectral inputs
before merge. Calibration conclusions remain sensitivity-only; no abundance,
identity, line significance or redshift conclusion changed.

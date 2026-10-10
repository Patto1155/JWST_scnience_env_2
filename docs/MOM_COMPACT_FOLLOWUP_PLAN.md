# Exact reference and compact independent spectrum pilot

Predeclared before second-round queries, 2026-10-10. Dependency: frozen public
metadata audit0798741; independent review requested. No outcome is assumed.

Question A: what does the actual wavecorr0005.rmap select for MoM's
NRS_MSASPEC observation at MJD60781 under context1535 and latest1596? Are the
selected reference's pedigree and provenance empirical or DUMMY? Predictions:
an applicable empirical reference may justify a calibrated alternate reduction;
the same DUMMY file would preserve the existing sensitivity-only contract.
Context/version changes alone do not establish better calibration. Verify the
selector chain and whole selected file, reuse an existing hash-verified file
when identical, and never double-correct existing CAL wavelength arrays.

Question B: can compact CAPERS release pixels/settings verify source identity,
disjoint contributors and usable wavelength coverage without full CAL/RATE
downloads? MoM's catalog source277193 and CAPERS102896 are within0.031arcsec,
but positional agreement alone does not prove one astrophysical emitter. The
metadata pilot found 18 CAPERS exposure roots, not nine; verify actual SLITS.

At z14.44, N IV1483/1486, C IV1549, HeII/OIII1650, NIII1750 and CIII1908 lie
approximately2.29,2.39,2.55,2.70 and2.95um, outside the indexed3.94–5.50um
CAPERS interval. Those pixels cannot directly tighten these UV nitrogen lines.
The weak catalog z6.13832 instead puts Halpha6563 near4.685um, with NII6584
and SII6717/6731 nearby, potentially inside the interval. A line-family test
would be conditional on attenuation/continuum and extraction adequacy, not
proof from a grade1 catalog redshift or mandatory Halpha for every low-z model.
Geometry/pixel validity may make even this test uninformative.

Budget: maximum eight new HTTP endpoints, five minutes, four MiB total accepted
response bytes. Applicable reference acquisition capped two MiB; compact
CAPERS spectrum/settings/PIXTAB capped two MiB total. HEAD before acquiring
compact products; if PIXTAB exceeds allocation, retain its metadata and stop.
No full CAL/RATE FITS, paid resources or people contact. Stop when selector,
pedigree and compact contributor/coverage inventory are verified, or document
access errors/size exclusions without treating them as public inaccessibility.

Validation: independent review of URLs/status/byte/hash receipts and exact
selector applicability; independent spectroscopy/PSF validation of any new
compact spectral pixels before measurement claims. Preserve old contracts.

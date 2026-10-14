# E: prospective pole-field metadata feasibility, 2026-10-14

This is a new sample; the historical Taurus design is unchanged. No new pole
archive or identity-query results have been inspected. Literature/mission
metadata may inform this freeze. Freeze commit must precede identity/SIA access.

## Selection and gate
Query SIMBAD basic identity metadata for YSO/T Tauri classes within 10 degrees
of either ICRS ecliptic pole (270,+66.560708;90,-66.560708 degrees). Sort by
pole distance then main_id; retain the first 10 per pole, with no replacements
chosen using flux or variability outcomes. Catalogue classes are identity
screening, not independent spectroscopic confirmation. Retain published coordinate
bibcodes. Query both official QR2_deep and QR3_deep SIA collections at each target;
all-sky images do not establish deep-field membership. The southern deep field is
shifted away from the LMC (mission documentation): a pole cone alone does NOT
establish membership in the shifted field.

Deduplicate physical observations by (obs_id,detector), not release. Fixed
broadband source scope is 2.8--3.9 microns, covering water ice and adjacent
continuum. A visit is a UTC-day bin (floor MJD), requiring >=8 independent,
nonoverlapping source channels and >=80% top-hat integrated wavelength coverage
within the fixed scope; all assembled channels span <=24 hours. Separate days
must be >=1 day apart; minute dithers do not supply independent wavelength bins.
SIA whole-detector em_min/em_max is NOT a source channel. Only a documented
metadata source-wavelength field can certify eligibility. No spectral WCS range
reads, pixels, photometry or lightcurves in this metadata-only arm.

Controls: five nearest catalogue normal field stars within 0.5 degree and
+/-1 mag 2MASS K relative to each target, ordered distance/main_id, excluding
YSO/T Tau and known variable classes. Require their deep membership and identical
source-channel visit eligibility. Catalogue nonvariability is not empirical
constancy; it only defines controls for a prospective null.

The gate passes only with >=5 targets having >=8 certified visits each and
matched eligible controls in the same field. Unknown coverage cannot pass and
must not be called zero visits, zero flux or null variability. If the gate fails,
stop this arm without science downloads; if services fail record access blocked.

## Conditional subsequent science
Only after a pass: review primary literature for variable ice-band optical depth;
freeze a separate design for changes in water 3.0 and CO2 4.27 micron absorption
relative to local continua with field-star null, noise model and multiplicity.
CO2 also requires independently certified simultaneous assembled coverage near
4.27 microns. No novelty assertion from an incomplete literature search.

## Acquisition limits and outputs
Metadata <=30,000,000 response-body bytes, science pilot <=500,000,000 bytes only
following the pass and second committed freeze; >=5,000,000,000 bytes free.
Count failed-response bytes, record URL/status/time/hash. New acquired raw bodies
are not committed. Record reduced exact identity/exposure metadata and receipts
under research_output/calibrated_20261014/e_*. Deliver
 docs/YSO_POLE_FEASIBILITY.md and budget fragment. No GOODS-N, state edits,
science claims or promotions. Software tests are not empirical controls.

# New-observable discovery campaign — 12 October 2026

Resume from merged PR82, `4bceeeef3063871ff6f540f49dad81001001dcef`.
The checkout was clean; live master was fetched and no open PR was returned.
The previous 746-pass validation is a baseline receipt, not a new rerun.

Objective: novel, defensible astrophysical findings worth sharing. Search
different public surveys and additional epochs. A newly characterized object
or conditional empirical relation can be valuable without identifying a unique
physical cause. A known broad topic does not rule out a genuinely new target
or prediction. Distinguish unconfirmed leads, replicated known results, and
validated new observations.

Three GPT-6.1 Sol high specialists scout time-domain infrared/optical data,
repeat spectroscopy, and stellar light curves. A fourth independently reviews
designs and promising measurements. Exploratory searches are allowed and
labeled; freeze candidate selection and follow-up questions before examining
new confirmation data. Authors are not sole validators. Do not expand protocols
or platform code merely to replace absent scientific information.

Fresh resource limits: free public services, no external-person contact.
Each initial scout may acquire 30 MB; each selected pilot may use 300 MB total
scientific response bodies and ten minutes per numerical run. Initial aggregate
scientific-data ceiling is 1 GB. Record source URLs, body sizes and hashes;
metadata traffic is separately qualified. The coordinator may explicitly raise
a justified limit before acquisition. No inherited allowance is assumed.

Do not repeat the stopped research4 screens or weaken their cuts. GOODS-N
outcomes remain unopened. Source54611 is a measurement discrepancy, not a
physical discovery. The rotation table is not a future strictly blind holdout.
Trusted coding-agent work is authorized under AGENT_RULES section2; runtime
worker sandbox restrictions remain intact.

## Executed rounds

1. Three specialists checked metadata and primary literature for new infrared,
   repeat-spectroscopy and stellar time-series observables. The independent
   reviewer challenged identity, selection, masks and actual epoch independence.
2. The selected pilots acquired NEOWISE and ZTF photometry, eight TESS QLP
   sectors, and SDSS/DESI spectra. Outcomes and failed selection criteria remain
   visible; no result is promoted merely because its data were acquired.
3. Independent numerical implementations checked the time series and stellar
   fits. The stellar author then traced the infrared object's prior identity
   through coordinate-based catalogs. The spectroscopy screen expanded,
   prospectively for the additional objects, to 36 distinct galaxies after
   deduplication and a published-event exclusion.
4. DDE 54's historical infrared pattern motivated a frozen prediction for
   August 2026 SPHEREx observations. A separate specialist reviews the image
   extraction, wavelength assignment, PSF normalization and spectral coverage.
   J111855 receives one explicitly exploratory second-line diagnostic after
   failing the original narrow-control gate; that diagnostic cannot retroactively
   pass the original experiment.

## Results and claim boundaries

| Pilot | Actual added evidence | Current interpretation |
|---|---|---|
|DDE 54, initially selected as VarWISE J035034.07+353508.5|NEOWISE visit controls, separately measured ZTF optical photometry, and 11 new-epoch SPHEREx image extractions|Three historical infrared faint states have approximate four-year spacing. The frozen median optical state contrast is consistent with zero; optical variability itself is substantial. SPHEREx does not confirm the predicted faint state, and a new period or mechanism is not established.|
|CLASS–DESI galaxies|36-object exploratory screen; distinct DESI epochs where available|No object passes the full frozen fading gate. J111855 has a conditional line contrast with weak narrow controls and persistent baseline quality flags.|
|KIC 8164262|Eight TESS sectors, 2019–2024, independently remeasured|Joined 2024 small-aperture mode amplitudes are approximately 598±56 and 607±52 ppm, with white-noise errors only. An apparent raw decline is sensitive to background/centroid terms; no robust physical evolution is detected.|

DDE 54 was already a variable YSO candidate in the 2017 VSX registration,
with earlier optical eruptions described there. Its prior identity was absent
from the initial SIMBAD lookup; absence from one service is not novelty evidence.
The possible new contribution is a tested temporal characterization of a known
object. The optical null applies to specified broad time windows and medians,
not to every timescale, lag or physical driver.

Detailed evidence: [infrared identity](RESEARCH5_IDENTITY.md),
[time-domain measurements](RESEARCH5_TIME_DOMAIN.md),
[independent SPHEREx review](RESEARCH5_SPHEREX_REVIEW.md),
[spectroscopy](RESEARCH5_SPECTRAL.md), [stellar measurements](RESEARCH5_STELLAR.md),
[independent stellar review](RESEARCH5_STELLAR_REVIEW.md), and
[independent scientific review](RESEARCH5_REVIEW.md).

## What the new satellite data actually test

The SPHEREx frames are from August 2026, independently observed after the
NEOWISE time series. Eleven selected exposures sample one eight-day campaign,
not eleven independent visits. Independent extraction rejects one heavily
masked image and one detector-edge image. The accepted channels cover only
about 18% of the nominal W1 response; the almost complete wavelength *hull*
would misleadingly count unobserved gaps as data. No synthetic W1 magnitude
is reported and the original two-visit, band-coverage gate fails.

At 3.2871 microns the independently measured flux density is approximately
6.47±0.14 mJy (formal diagonal-variance error), with background/aperture/PSF
checks. It looks bright relative to the simple faint-state prediction, but a
narrowband point is not a WISE magnitude. These observations neither confirm
the proposed recurrence nor, without adequate bandpass coverage or a stated
spectral model, establish its definitive rejection. The new result is a
quality-audited partial 2026 spectrum and a constrained follow-up question.

The galaxy's separately authorized 5720 diagnostic is likewise compatible
with weakening, but its baseline detection remains below the original S/N
requirement and is sensitive to the integration window. The original
36-object discovery shortlist remains empty. A corrected data-quality policy
and an exploratory second test do not retroactively pass a failed gate.

**No new astrophysical discovery is established in this campaign.** The
source-specific measurements, negative tests and remaining candidates are
preserved rather than converted into a mechanism or population claim.
GOODS-N outcomes remain unopened throughout.

## Highest-value next actions

1. For DDE 54, check earlier SPHEREx QR2 metadata for genuinely missing
   wavelength coverage and a distinct observing campaign before downloading
   further images. A repeat reduction of the same exposure is not new data.
   Complete W1-weighted coverage and validated cross-band calibration are
   needed before calling the 2026 state faint or bright on the WISE scale.
   Preserve the known optical eruptions and substantial current optical
   variation in any interpretation.
2. For J111855, resolve the flagged SDSS baseline using exposure-level
   extraction/sky information and obtain a defensible aperture/control
   comparison. More fits of the same weak controls cannot supply that evidence.
   Until then retain it as an unconfirmed line-weakening lead, not a TDE.
3. Retain KIC 8164262 as a measured baseline. Reopen an evolution search only
   when additional independent epochs or better photometric calibration add
   sensitivity; the same processed light curves do not establish damping.

## Validation and acquisition accounting

The configured full quality gate passes **767 tests with three expected
missing-input skips** (770 collected, zero failures/errors). All 65 installed
distributions match the exact lock. A final formatting-only repair is checked
by AST equivalence and strict lint/format checks without repeating unrelated
tests. [Consolidated validation](RESEARCH5_VALIDATION.md) records the exact
tested and final code identities, logs and input binding checks.

Recorded response-body accounting is 78.86 MB for the time-domain work
(including 55.00 MB of SPHEREx range responses and a 22.42 MB literature PDF),
39.28 MB for the spectral work, 3.47 MB of stellar light curves, and 0.145 MB
of identity metadata. These have different metadata/documentation scopes and
are not asserted to be a complete global wire total. One early arXiv HTML
probe was unmetered, explicitly retained as an accounting limitation in the
time-domain ledger. Bulky intermediate range payloads and full papers are
not repository deliverables; compact scientific arrays and their provenance
are retained. No paid service or external-person contact was used.

Repository publication follows independent review and hosted CI; the release
link and immutable tree are recorded after creation of the reviewed snapshot.

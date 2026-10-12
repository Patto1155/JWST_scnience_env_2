# Discovery portfolio and bounded FRB pilot, 12 October 2026

No new physical discovery follows from this portfolio screen. The first-choice
non-JWST test was acquired, executed and independently counted; it failed its
predeclared data-coverage gate. The remaining questions are potentially useful
prediction tests, not promises of novelty or discovery. Broad subjects being
published does not exclude new tests, and search silence never proves novelty.

The requested objective was flexibility 5/5, ambition 4/5, platform work 1/5:
prefer a small observational discriminant with independent controls over a new
infrastructure layer. Prior MoM nuisance-grid forecasts and the already-studied
NEXUS epochs are not reopened by this report.

## Round 1: three concrete physical questions

| Question | Independent discrimination | Novelty boundary | Session decision |
|---|---|---|---|
| Do repeating FRBs show coherent within-source DM–scattering co-variation? | Same-source changes remove constant Galactic/IGM columns; chronological halves and source weighting control leverage. Resolved, broad-band, simple bursts reduce intrinsic drifting confounding. | Individual DM/scattering evolution and across-source correlations are already studied. A controlled *within-source covariance* is only potentially different. | Initially preferred: public 4 MB catalog. Executed; coverage failed. |
| Does rotation disagreement between coeval wide pairs track passage through the intermediate-period gap, after harmonic aliases and unresolved multiplicity are controlled? | Wide-pair coevality; matched-mass pairs; independent observing sectors; random mass/color-matched pairs as a control. | Wide-pair gyrochronology consistency, the fully convective discontinuity, and M-dwarf twin mismatches are published. A mass-ordered, gap-specific transition prediction requires a separate focused novelty check. | Plausible different direction; current complete public TARS catalog exceeds the 100 MB acquisition cap. Do not download automatically. |
| Does the extra near-IR thermal component required by dense-gas LRD spectra predict independent MIRI colors across GOODS fields? | Fit spectral/Balmer information in one field; freeze thermal prediction, then assess unused MIRI bands/field with neighbor controls. | A stellar bump, weak hot dust, and dense-gas fits needing 800–1400 K extra emission are already known. Novelty requires a specific predictive residual, not another flexible SED fit. | Lower priority: exact catalog exists but deblending and model freedom weaken a small-session claim. No outcome inspection/download. |

### Physical and literature checks

FRB primary release: Abbott et al.,
https://arxiv.org/html/2601.09399v1. Catalog 2 has 4539 events. Its model uses
global DM/scattering per event, independent spectral parameters per sub-burst,
fixed dispersion/scattering frequency indices, and an F-test choosing zero or
free scattering. This makes sub-burst duplication and censoring essential.

Curtin et al., https://arxiv.org/html/2411.02870v2, investigates 124 bursts
from 35 repeaters at high time resolution, including temporal DM/scattering
slopes and extragalactic-DM versus scattering. Section IV.3 warns that fitburst
DM can be biased by complex burst morphology; IV.4 discusses scattering versus
downward drifting. A catalog correlation cannot replace a structure-based DM.

Cook et al., https://arxiv.org/html/2605.08410v1, sections III.5 and V.3 were
checked directly. Forty sources had >=4 events in their DM-evolution screen;
they use constant/linear fits, BIC and simulations, reject outlier-dominated
cases, and retain four new tentative linear trends plus two previously studied
sources. Section V.3 explicitly discusses drifting-induced DM bias and an
upcoming raw-voltage investigation. Re-finding those trends is not novelty.
Their across-source correlations concern rate, duration, fluence and excess DM;
that does not establish novelty of our proposed covariance statistic.

TARS primary https://arxiv.org/html/2603.05586v2 reports 1,046,317 default
period detections and a harmonic-correction method. Its independent literature
agreement is roughly 85–90%, so period disagreements require per-sector checks.
Relevant direct priors are Gruner et al.
https://arxiv.org/abs/2307.10836, Chiti et al.
https://arxiv.org/abs/2403.12129, and Couperus et al.
https://doi.org/10.3847/1538-3881/ae34ad. These already cover coeval rotation,
the convective-boundary feature, and twin mismatch respectively.

For LRDs, Ronayne et al., https://arxiv.org/abs/2508.20177, already analyzes
eight spectroscopic LRDs with NIRCam/NIRSpec/MIRI and tests stellar, AGN and
dense-gas interpretations. DR5 catalog methodology and MIRI fields are in
https://arxiv.org/html/2601.15956v1 (Appendix A.10). A free extra thermal
component can erase discrimination, so the alternative must be a frozen
prediction with limited extra degrees of freedom.

### Exact public endpoints and byte feasibility

All endpoints below were checked as public metadata during this session;
only the FRB CSV was acquired as scientific data.

* FRB CSV, successful full acquisition:
  https://www.canfar.net/storage/vault/file/AstroDataCitationDOI/CISTI.CANFAR/25.0066/data/table/chimefrbcat2.csv
  — **4,057,396 bytes**, SHA256
  `5108ada779d279a2547d9f9e73ae25bfdd40d8496d6ba7255ec29c6629057a48`.
  Permanent table listing:
  https://www.canfar.net/storage/list/AstroDataCitationDOI/CISTI.CANFAR/25.0066/data/table.
* TARS metadata API https://zenodo.org/api/records/19917941 returned the exact
  manifest. Minimum complete compressed table:
  https://zenodo.org/api/records/19917941/files/tars_table_2.csv.zip/content
  — **136,182,994 bytes**; feather is 230,796,866 bytes. Sector table is
  13,372,075,946 bytes (feather). The 82,732,764-byte validation ZIP is not a
  population substitute. No small complete subset endpoint was demonstrated.
  Per-target light-curve documentation: https://archive.stsci.edu/hlsp/tars.
* JADES DR5 GOODS-S listing:
  https://slate.ucsc.edu/~brant/jades-dr5/GOODS-S/hlsp/catalogs/,
  with exact photometry product
  https://slate.ucsc.edu/~brant/jades-dr5/GOODS-S/hlsp/catalogs/hlsp_jades_jwst_nircam_goods-s_photometry_v5.0_catalog.fits.
  The MIRI HDU is inside that product. Full body size and a <=100 MB subsetting
  route were not demonstrated; do not imply that a full download fits the cap.
  Spectroscopic identities/products are separately available at
  https://jades.herts.ac.uk/DR4/Combined_DR4_external_v1.2.1.fits.

## Round 2: executed FRB coverage experiment

The immutable pre-outcome contract is [RESEARCH4_FRB_FREEZE.md](RESEARCH4_FRB_FREEZE.md).
Its SHA256 is `45aa555099ae50554188230da2efe736af8735ad98025e3952ca78de3fbd064c`.
Selection requires nominal flags, S/N >=20, a single catalog sub-burst,
measured scattering/error >=5, >=200 MHz bandwidth and >=2 temporal bins of
scattering at the emission peak. The primary response would be log scattering
at the fixed reference frequency 400.1953125 MHz. Scattering at peak is only
a resolution cut. Six sources with >=6 qualifying events are required before
any association is evaluated. Earlier floor(n/2) events and later events form
the fixed chronological halves.

Results: **5045 rows, 4539 events; 29 qualifying events across 19 source
labels; maximum four events/source; zero sources meeting six-event coverage.**
The experiment stopped before DM–scattering covariance, half correlations or
significance were computed. Eighty-three nonempty repeater labels in the file
are a catalog-string diagnostic, not an independently adjudicated physical
source count or a contradiction of the paper's eighty-source sample.

The independent oracle reproduced final counts and source membership; see
[RESEARCH4_ALTERNATIVE_FEASIBILITY.md](RESEARCH4_ALTERNATIVE_FEASIBILITY.md).
Reject-attribution order differs between implementations but final selection
must agree. No screen was weakened after this failure. The question remains
unanswered; this is neither evidence for nor against changing FRB plasma.

The planned conditional Cauchy bound on random same-fit noise covariance is
not a bound on morphology bias, fixed-index error, or shared systematics.
Fivefold error inflation would be an uncalibrated sensitivity, not certified
uncertainty. Zero-scattering model selections are neither physical zeros nor
reported numerical upper limits. Detection-only inference cannot yield the
population incidence of variable environments.

## Round 3: reopening and next decision

A <=20 MB, <=5 minute metadata reopening checked the official portal and
archival high-time-resolution routes. The current portal explicitly links
Baseband Catalog 1 DOI https://doi.org/10.11570/23.0029, with public archive
https://www.canfar.net/storage/list/AstroDataCitationDOI/CISTI.CANFAR/23.0029/data.
The separate https://doi.org/10.11570/23.0004 is the 2023 repeaters catalog,
not the high-resolution baseband catalog. Catalog 2 dynamic spectra are at
https://www.canfar.net/storage/list/AstroDataCitationDOI/CISTI.CANFAR/25.0066/data/dynamic_spectra
but retain millisecond sampling and do not solve the resolution blocker.

The Baseband Catalog 1 README was retrieved. It documents HDF5 beamformed
voltages/intensities, frequency/time maps and coherent-dedispersion attributes,
but does not supply a joint DM/scattering posterior. The displayed
`beamformed_files` listing contains sampled products of 1.52–2.26 GB each
(e.g. `FRB20181213A_22310619_beamformed.h5`). These exceed the acquisition
cap, and no small processed repeated-source subset was demonstrated. Listing
pagination was not exhausted; the displayed rows are not the total archive.
The metadata receipt is `research_output/research4_frb_reopening_metadata.json`.

No archive manifest connecting six qualifying repeated high-resolution events
for each of six sources, with usable structure-DM and scattering information,
was demonstrated in this bounded search. No released joint DM/scattering
covariance or free-scattering-index posterior was demonstrated. This is a
scope-limited availability result, not an assertion that no such public data
exists. Do not substitute the existence of individual high-resolution bursts
for a viable repeated-source population or download all voltage data.

The immediately actionable decision is **stop this FRB covariance track**.
Reopening requires a concrete public repeated-burst manifest plus timestamps,
time/frequency resolution, noise/mask definition and structure-DM information,
or a new model-specific test that does not depend on those absent quantities.
The rotation-gap/coeval-pair test was then assessed as a genuinely different
direction in Round 4. The coordinator raised its separate body budget to
160,000,000 bytes, so the former 100 MB ceiling no longer excluded TARS.
The small reference table provides 372 pairs; 207 have both parallaxes >2 mas
and both Gaia G<16. Actual TARS paired overlap remains unmeasured. The precise
primary review found that generic signed rotation inversions and nonmonotonic
coeval sequences are already discussed; no independent narrow-band enrichment
prediction was justified before outcomes. It was stopped before downloading
136 MB or consulting new period outcomes. See
[RESEARCH4_ROTATION_FEASIBILITY.md](RESEARCH4_ROTATION_FEASIBILITY.md) for the
bounded executable reopening gate and
[its independent review](RESEARCH4_ROTATION_FEASIBILITY_REVIEW.md). This does
not alter the FRB freeze.

## Retention and verification

The actual public CSV is retained losslessly as
`data_sources/research4/chimefrbcat2.csv.gz`, deterministic gzip mtime=0,
**1,664,400 bytes** (compressed SHA256
`f1e954fd05c128d45a1a8af8a9f011393cffd3370f6dbb7a46c421a7033114be`).
Acquisition took 22.3 seconds. Metadata transfers are separate from these
body counts; no combined exact transfer total is claimed. Reports and receipts
distinguish public observations, selection output and synthetic verification.

```bash
/tmp/jwst-handover-env/bin/python -m discovery.research4_frb_pilot \
  --catalog data_sources/research4/chimefrbcat2.csv.gz \
  --output research_output/research4_frb_results.json
/tmp/jwst-handover-env/bin/python -m pytest tests/test_research4_frb_pilot.py -q
```

The numerical run took about 0.1 seconds. Four targeted tests pass, covering
zero-model/missing-error handling, event/sub-burst identity, constant-data
association output, and deterministic odd-count time halves. Ruff check and
format pass for the author files. Software verification is not discovery
evidence. No paid service or external-person contact was used.

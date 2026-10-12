# GOODS-S calibration pilot and conditions for a GOODS-N test

This is a frozen, bounded **released-coadd measurement pilot**, not a physical
Balmer-anomaly discovery protocol ready for GOODS-N. GOODS-N outcome columns
remain unopened. The draft uses only GOODS-S outcomes and public release
documentation. Calibration, covariance and novelty are unresolved gates.

## Executed design frozen before acquisition

The exact manifest is `research_output/research4_jades_manifest.json`, SHA256
`3c181df81355e35afd738f0b390981e4dae7b1e92b11d0cd5cda4688676e2872`.
The input catalog SHA256 is
`4b4e7fd4306208ee801406c7ed73fdab895a2e67184af7f639a91e5f9c8ab7d4`.
Read the catalog field column, subset `GS`, then access GOODS-S metadata.
No line flux, line SNR, decrement, prism outcome or aperture result enters
selection. The full GOODS-S catalog contains 3,387 observation rows.

1. Require redshift flag A/B and positive exposure in both G140M and G235M.
2. Predeclare lower-redshift `2.45 <= z < 2.60` and control
   `2.70 <= z < 2.90`. These are redshift groups, not verified edge groups.
3. Exclude the previously inspected training objects 7496 and 8656.
4. Sort each group by decreasing minimum paired exposure, then lexical
   Unique_ID. Suppress an already retained positive DR5 identity or a source
   within 0.2 arcsec. Retain the first six per group. No replacement after any
   download, coverage, fit, sign or precision failure.

There are 71 and 83 metadata-eligible observation rows before exclusions and
deduplication. This is an exposure-biased targeted sample, not an estimate of
galaxy prevalence or a random sample of the catalog.

| Group | Six frozen NIRSpec IDs |
|---|---|
| Lower redshift | 54611, 10011378, 203602, 42645, 43697, 48912 |
| Interior redshift | 20313, 283952, 7586, 8102, 52538, 10009703 |

Acquire only the two medium-resolution x1d products for each frozen target:
`f070lp-g140m` and `f170lp-g235m`. The whole pilot has a 100,000,000-byte
download cap and 300-second numerical-fit cap. Store URLs, body sizes,
SHA256, target identities, failures and compact released arrays. Public
endpoint failures remain missing observations; they do not authorize a new
target or a budget increase.

## Measurement and coverage contract

Primary measurements use `EXTRACT5PIX1D/FLUX` and supplied `FLUX_ERR`.
Fit vacuum Hb 4862.68 Angstrom and [OIII] 5008.24 Angstrom in each grating,
using the existing bin-integrated Gaussian plus linear continuum in fixed
`+/-0.015 micron` windows. The predeclared widths/center bounds are those in
`tools/jwst/jades_balmer_pilot.py`; never widen bounds on individual targets.
Require convergence, full normalized-Jacobian rank and no active bounds.
Otherwise scientific fit parameters are null and diagnostics remain separate.

For each line validate a finite strictly increasing uniform wavelength grid,
then require >=90% finite positive-error coverage in the primary
`+/-0.0035 micron` box, >=2 line bins and >=4 red-sideband bins at offsets
`+0.008..+0.015 micron`. Coverage is summed from actual bin intersections,
not the fraction of pixel centers. Report actual predicted Hb distance from
the first finite positive-error pixel in each grating, masked coverage and
failures. These are diagnostics; the redshift groups are not reclassified
after seeing them. Gaussian fits and box integration need not coincide because
their continuum and wings differ.

Retain negative identifiable flux estimates and errors in the measurement
table. A log endpoint is available only when all four primary measurements
have coverage, valid fits and strictly positive fluxes. Do not silently discard
negative results from selected counts or call unavailable measurements zero.

For each eligible source define

`D = log(Hb_G235M/Hb_G140M) - log(OIII_G235M/OIII_G140M)`.

An exactly gray multiplicative grating scale cancels algebraically. Nonzero D
can still arise from wavelength-dependent transport, different line morphology,
continuum/line modeling, coadd noise, contamination or calibration. It does not
identify the unbiased grating or the true Balmer decrement.

Report D values, group eligible counts, medians and sign counts. Require at
least four valid primary sources in **each** group; otherwise stop the group
comparison. No calibrated sigma, p-value, permutation probability or causal
edge effect is claimed. Missing/positive-only eligibility and exposure,
redshift, morphology and observing-program imbalance prevent an unconditional
population interpretation. The minimum four is a practical availability gate,
not a power calculation.

## Independent test and calibration limits

The independent reviewer imports no Gaussian candidate fit. It verifies
product identity and hashes, integrates actual bins in the fixed primary
`+/-0.0035 micron` box, subtracts a constant red-sideband continuum and reports
the same four line fluxes and D. The +/-0.0025 and +/-0.0045 boxes are
post-primary sensitivity checks. It applies the same >=90% box and >=4
sideband-bin requirements, preserving signed fluxes and availability.
Independent source selection reproduction must match all twelve identities
and ordering without reading any line outcomes.

3-pixel extraction and NOD2 values are dependent robustness checks. Box
integration and Gaussian fitting also use the same photons. Agreement supports
measurement-method robustness; it is not a new independent observation.
Released errors do not supply all spectral covariance, source-specific slit
transport, exposure-level independence or cross-configuration calibration.

Stop if the numerical method disagreement changes the apparent group direction,
if most measurements lack coverage/identifiability, or if valid group counts
fail the gate. A significant-looking diagonal residual does not override these
stops. Do not expand the catalog or tune windows to recover a desired finding.

## GOODS-N decision and multiplicity contract

Do **not** open GOODS-N to rescue this pilot. A worthwhile GOODS-N test needs a
specific prediction that survives GOODS-S review and a fresh novelty check.
The simplest instrument-follow-up prediction is replication of a frozen D
pattern under the same two redshift ranges and extraction contract. If pursued,
declare one primary aggregate D contrast in advance; list every secondary
line/configuration contrast and apply Holm familywise correction at 0.05 across
any inferential family. No significance will be computed until a credible
sampling/noise model handles covariance, selection and observing-program
dependence. Failed quality measurements stay in the selection accounting.

A physical Ha/Hb test is a separate experiment and remains blocked. Before
opening its holdout outcomes, it must freeze: a physical null envelope allowing
temperature/density rather than treating 2.65 or 2.86 as universal atomic
bounds; same-configuration coverage; independent Hb overlap verification;
calibration and absorption nuisance bounds; source-grouping; and an end-to-end
null simulation through the actual SNR/representative selection. The test family
must include every eligible heldout source examined, not only low-ratio leads;
Holm/Bonferroni control applies across those source hypotheses and any searched
endpoints. Shared apertures/nods cannot increase the independent test count.
GOODS-S control residuals cannot certify a source-specific systematic bound
from two previously selected anomalous targets.

Only after nuisance and selection calibration should a source be declared a
confirmed statistical measurement anomaly; independent exposures/reduction or
externally calibrated data remain required for stronger physical interpretation.
If those requirements cannot be met with released products, stop the physical
Balmer track and preserve GOODS-N for a different preregistered question.

## Reproduction

Use `/tmp/jwst-handover-env/bin/python` with one BLAS thread:

```bash
python -m tools.jwst.research4_jades_pilot freeze \
  --catalog /tmp/jades-dr4-pilot/Combined_DR4_external_v1.2.1.fits \
  --manifest /tmp/research4-freeze-recheck.json
python -m tools.jwst.research4_jades_pilot run \
  --manifest research_output/research4_jades_manifest.json \
  --data-root /tmp/jades-research4-gs \
  --download-receipt research_output/research4_jades_acquisition_run.json \
  --output /tmp/research4-jades-replay.json
```

The local full catalog and the original eight GOODS-S products already exist;
this design acquires at most 24 new small x1d products. Exact actual execution,
byte counts, outcomes and stop decision belong in the separate pilot receipt,
not this pre-acquisition statistical contract.

Primary reference: Scholtz et al., JADES DR4 Paper II,
https://arxiv.org/abs/2510.01034. The release describes point-source-optimized
slit-loss/background treatment and both extraction widths. The preceding
`JADES_BALMER_PILOT.md` and `RESEARCH3_JADES_INDEPENDENT_REVIEW.md` document the
7496 grating discrepancy and the limits of aperture stability. This protocol
does not claim that this general calibration issue is novel.

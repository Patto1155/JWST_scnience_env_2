# Independent-line selection: frozen arm C, 15 October 2026

This is a prospective conditional released-product comparison, not an
independent-photon experiment. No new catalog or spectral outcomes have been
opened by C. The earlier claim that selecting a different line *makes* its
measurement noise independent is a hypothesis, not a property of line identity.

## Freeze before access

Use the canonical GOODS-S JADES DR4 v1.2 line catalog and EXTRACT5PIX1D v2.0
spectra, with unchanged `calibrated_population.marginal_fit` (signed flux;
41 by 41 nodes; no positivity restriction). Exclude every unique object in
both halves of `research_output/calibrated_20261014/b_frozen_draw.json`.
Never open GOODS-N or southern heldout spectral arrays. Catalog identity and
published flux/error access are selection information, not blind outcomes.

Create two directional strata: select O3_5007 to measure HBaB_4861, and
select HBaB_4861 to measure O3_5007. Require GS, positive finite z, finite
positive selector error, selector S/N in [5,30], both lines inside 0.7–5.3 um,
and each catalog configuration one of the four supported medium modes.
Do **not** select, rank or truncate on target flux, target S/N, target flux/error
finiteness, target positivity or fit success. An absent target catalog value
stays a missing comparison in the selected denominator. Metadata-only coverage
requirements do not imply usable spectral coverage.

Sort IDs; seeded PCG64(20261015) permutes candidates in each stratum; take
15 from each in fixed alternating order, preventing object reuse across strata.
If fewer than 30 disjoint objects qualify, stop as insufficient eligibility;
no replacements or changed cuts. Commit identities and numerical predictions
before spectral HEAD/GET. No retries or replacement on fit failure.

A's final committed regression coefficients and scatter will be imported
verbatim by model key, with its source SHA and file hash, before spectra.
H1 predicts constant log ratio a; H2 predicts a+b/SNR_target (and the separately
frozen inverse-square model is secondary). Never extrapolate 1/SNR through
zero or treat a target S/N outside A's 5–30 range as calibrated prediction.
All out-of-range rows remain in the sample, with extrapolation flags.
If A coefficients are unavailable, do not open C spectra.

## Statistics and decision

Report all 30 selected rows and failures; per-row signed flux differences,
paired log ratios where both fluxes are positive, and the number excluded from
log summaries. Log summaries are positive-pair descriptive summaries and cannot
establish an unbiased population result when any nonpositive pair is omitted.
Use no quadrature error denominator. Report median log ratio, SD and raw MAD,
exact two-sided sign test about a, 10,000 object bootstrap 95% percentile CIs
(seed 20261015), and both directional strata separately. No shared object may
cross directions. Report measured target S/N without using it for selection.

For positive target catalog S/N, regress log ratio on 1/SNR_target; compare
frozen H1/H2 squared residual sums on the same finite positive pairs. Bootstrap
the slope and difference RSS(H1)-RSS(H2). Prefer a hypothesis only if its
bootstrap 97.5% interval excludes zero in the matching direction (two primary
contrasts: slope and model-RSS difference; Bonferroni family alpha .05).
Flatness requires equivalence, not a nonsignificant slope: the 97.5% slope CI
must lie in [-0.25,+0.25] and median-log-ratio-minus-a 97.5% CI in [-.05,.05].
If fewer than 24 valid positive pairs or fewer than 10 per direction, or any
unresolved selection covariance, report inconclusive for H1 versus H2.
All significance is conditional on observed S/N, an errors-in-variables covariate;
ratio/denominator coupling can itself generate a trend without target truncation.

## Correlation control

Measure selector and target line-free residual correlations in matched wavelength
coordinates from their actual compact spectra, with object bootstrap. Continuum,
extraction, sky subtraction, flux calibration and redshift can couple lines even
in different gratings. A null correlation estimate is not proof of independence.
Run joint Gaussian selection-noise simulations at rho=-.5,-.25,0,.25,.5 using
at least 10,000 objects per cell: selection is on noisy selector S/N only;
latent target/selector flux correlations are .0,.5,.9 and marginal intrinsic
log-flux SD=.7. Preserve the selected sample denominator and count invalid log
pairs; these are sensitivity models, not measured source covariance. A clean
H1 preference requires the observed contrast to remain under every plausible
covariance scenario informed by residuals; otherwise report conditional and
inconclusive. Physical correlations change the target S/N and line-ratio mix,
so stratify direction, grating and selector S/N [5,8),[8,30]; never claim the
same target population as the original target-selected cohort. Shared-photon
catalog/refit covariance is additional to cross-line selection covariance.

## Budget and stop

C cap is 1,073,741,824 cumulative received science/catalog bytes, including
partial/failed transfers; keep 5,000,000,000 free bytes after reservation.
The historical GS catalog length is 62,752,320 bytes, leaving 1,010,989,504
for up to 30 spectra; actual spectrum lengths require HEAD before GET.
Require bounded Content-Length, charge chunks before bounds checks, checksum
and header identity/units checks, normalize, save compact arrays and receipts,
then delete raw bodies in finally. A policy denial stops the network arm;
no alternate hosts, proxy bypass, mirrors or transport retries.

The committed implementation covers selection, catalog normalization, numerical
summary and synthetic covariance sensitivity. Acquisition integration and real
residual-correlation estimation require data and remain unexecuted if blocked.

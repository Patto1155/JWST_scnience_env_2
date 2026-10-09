# Atomic-informed yield comparisons: what survives reduction and ionization uncertainty

9 October 2026. This continuation conditions four versioned SMS yields and four
selected rotating-star benchmarks on the new PyNeb ionic calculation. It does
not identify an enrichment mechanism or measure an elemental abundance.

## Reproduction and evidence contract

```bash
python -m discovery.atomic_enrichment \
  --ionic-report research_output/mom_ionic_fit.json \
  --grid research_output/mom_atomic_grid.json \
  --spectrum research_output/mom_z14_point_resolution.json \
  --output research_output/atomic_enrichment_coadd.json
python -m discovery.atomic_enrichment \
  --ionic-report research_output/mom_native_ionic_fit.json \
  --grid research_output/mom_atomic_grid.json \
  --spectrum research_output/mom_native_reduction.json \
  --output research_output/atomic_enrichment_native.json
python -m pytest tests/test_atomic_enrichment.py tests/test_enrichment_constraints.py \
  tests/test_chemistry_identifiability.py -q
```

The compact outputs pin the ionic, atomic-grid, spectrum and benchmark bytes.
The generator refuses inconsistent receipts, empty/duplicate grid cells,
nonpositive covariance, inconsistent cached Fieller summaries, or treating
shared-data scenarios as independent likelihoods. No optional atomic solver is
needed to replay the saved grids. Regenerating the grid requires the versioned
PyNeb inputs documented by the atomic-model report.

In addition to hashes, an independent linear operator reconstructs each saved
ionic numerator/denominator and its covariance from the specified atomic
emissivities and source five-group flux/covariance. A self-consistent forged
ionic summary fails this replay even if its cached ratio and Fieller set agree.

Primary yield sources, exact table versions, solar conventions and model limits
are retained in `data_sources/pilot/enrichment_benchmarks.json` and
[the earlier enrichment report](ENRICHMENT_CONSTRAINTS.md). The four SMS models
start at 0.1 solar metallicity. They are specific models, not interpolation over
all possible SMS masses. The rotating models are rounded selected benchmarks,
not the entire allowed population. No absent WR carbon/oxygen yield or VMS
joint yield grid has been invented.

## The physical nuisance that a yield comparison must retain

PyNeb supplies emissivities, under a homogeneous common temperature/density,
optically thin collision-only C IV, the specified multiplet definitions and no
differential attenuation. The summed ionic quantity is

\[
 R_{\rm ion}=\frac{N^{2+}+N^{3+}}{C^{2+}+C^{3+}},\qquad
 \frac NC=R_{\rm ion}\,k,\qquad
 k=\frac{f_{C,\,2+\,+\,3+}}{f_{N,\,2+\,+\,3+}}.
\]

The carbon and nitrogen stage coverage fractions are unmeasured. Their ratio
can be below or above one; positivity alone gives no finite, useful lower or
upper bound. Temperature-grid variation does not calibrate these fractions.
Resonant transfer, stellar C IV, phase differences and extraction uncertainty
can also change the interpretation. No N/C posterior is transferred from Cue
to this ionic calculation.

For a carbon-bearing ambient phase and retained ejecta, the homogeneous mixed
N/C lies between the ambient and retained-ejecta ratios. Under equal retention,
the tabulated SMS ceilings are 1.470, 35.896, 40.382 and 12.393 by number. With
differential retention their ejecta ceilings multiply by `f_N,retain/f_C,retain`.
Equal element retention and equal ionic stage coverage are separate assumptions.

The likelihood comparison fits the two signed ionic measurements with their
full 2×2 covariance. It profiles a common nonnegative normalization over the
allowed ratio interval. A second fit over the whole positive quadrant defines
the conditional profile deviance. This retains negative observations rather
than clipping them to zero. A 3.841 reference deviance is a conditional
one-ratio Gaussian sensitivity threshold, not a calibrated mechanism probability,
model odds, or population significance. An independent whitened convex-cone
NNLS optimizer verifies the profile against 50 signed/correlated synthetic
controls; the controls do not validate observed noise distributions.

## Coadd-only conditional constraints

At 20,000 K and 1,000 cm⁻³, the nominal coadd ionic ratio is 8.828 with
conditional Gaussian 95% Fieller set [3.878,18.306]. The grid spans seven
temperatures and four densities. Different cells reuse the same observed
spectrum; neither 28 cells nor two LSF families are independent measurements.

| Selected equal-retention yield | Largest k reaching each nominal-grid ionic point | Largest k retaining overlap with each cell's conditional 95% lower endpoint |
|---|---:|---:|
| 1,000 solar masses | 0.079–0.244 | 0.186–0.568 |
| 10,000 solar masses | 1.924–5.951 | 4.548–13.868 |
| 50,000 solar masses | 2.165–6.695 | 5.116–15.601 |
| 100,000 solar masses | 0.664–2.055 | 1.570–4.788 |

These ranges describe deterministic atomic-cell variation, not a probability
distribution or a confidence interval on k. At fixed k=1 and equal retention,
the 1,000-solar-mass model has conditional profile deviances 7.20–10.72
across the nominal grid and 9.21–12.81 under the generic point-source LSF.
The other three SMS ceilings admit the data within the stated 95% reference
threshold. This tests the combined yield/ionization/retention/reduction
assumptions. It cannot exclude the stellar mechanism while k is free.

At the nominal reference cell, the selected 1,000-solar-mass yield requires
`f_N,retain/f_C,retain ≥ 6.00` to reach the ionic point if k=1. A ratio this
large is algebraically attainable with low carbon retention; its physical
plausibility is uncalibrated. The outputs include a sensitivity case with
100% nitrogen and 10% H/He/C/O retention rather than silently imposing equal
element retention.

## Independent native extraction and empirical noise

The native comparison uses the separately reduced, already nod-subtracted CAL
exposures and each of its four specified covariance/LSF families. Exact native
weights, original author PIXTAB and fully source-specific instrumental
calibration are unavailable. The empirical off-trace transport is a measured
noise sensitivity, not a guarantee of complete line-region covariance or a new
independent set of spectra.

The native formal and empirically transported families are kept separate. They
must not be multiplied by the coadd likelihood: these reductions reuse the
same source photons and shared nod backgrounds. The native empirical family
weakens the lower nitrogen constraint, making a coadd-only conditional yield
exclusion unstable. The saved native output gives every atomic cell, its
signed/bounded status and profile deviance rather than manufacturing a positive
abundance lower limit.

| Native treatment | 1,000-solar-mass fixed-k=1/equal-retention profile deviance range | Cells above conditional 3.841 reference |
|---|---:|---:|
| Nominal LSF, formal shared covariance | 4.56–8.12 | 28/28 |
| Generic point LSF, formal shared covariance | 3.90–7.07 | 28/28 |
| Nominal LSF, empirical off-trace transport | 1.95–3.51 | 0/28 |
| Generic point LSF, empirical off-trace transport | 1.68–3.03 | 0/28 |

No selected SMS ceiling conflicts at the reference threshold under either
empirically transported native family, even with k=1 and equal retention fixed.
Thus the stronger apparent yield discrimination depends on covariance/reduction
assumptions before the additional ionization or retention uncertainty is opened.
This compares conditional sensitivities, not independent repeated rejections.

The generic point empirical reference cell gives ionic ratio 6.461 with Fieller
set [0.146,21.708]. Four of its 28 atomic cells instead have sets crossing zero.
The output retains them explicitly and does not logarithmically transform
negative endpoints. A marginally positive conditional ionic lower endpoint in
one selected cell supplies no robust elemental enhancement or model exclusion.

## Gas parcel, carbon/oxygen and helium predictions

The calculation solves conserved H/He/C/N/O nuclei for each actual ionic point
or positive Fieller endpoint, specified k, ambient C/O, and explicit retention
fractions. It predicts ambient parcel mass, C/O, N/O, O/H and He/H. Signed or
unbounded sets do not become clipped positive abundance posteriors. These are
deterministic conditional endpoint predictions, not draws from a posterior.

For example, the nominal reference ionic point with **k=0.3**, carbon-poor ambient
gas `[C/O]=-0.65`, `[O/H]=-1.38`, initial solar N/C and full retention gives:

| Yield | Maximum ambient parcel mass (solar masses) | log C/O | He/H by number |
|---|---:|---:|---:|
| 1,000 solar masses | Unreachable | — | — |
| 10,000 solar masses | 1,060,399 | -1.053 | 0.08402 |
| 50,000 solar masses | 94,418 | -0.891 | 0.08667 |
| 100,000 solar masses | 966,703 | -0.816 | 0.09769 |

The ambient He/H is 0.08333. Ten-percent equal retention decreases these masses
by ten while leaving the endpoint elemental ratios unchanged. Differential
retention changes both ceilings and composition. These comparisons illustrate
why C/O, helium and emitting gas mass could discriminate selected yields after
ionization and retention are constrained. Current unresolved He II/O III] does
not independently measure helium or oxygen abundance, and no hydrogen line
supplies an emitting gas mass here. The sensitivity scenarios do not establish
galaxy-wide numbers of polluters.

Pristine dilution of the selected rotating benchmarks preserves N/C, C/O and
carbon-isotope ratios. The output therefore gives their required k and
conditional ionic profile fits at their fixed metal ratios, rather than
allowing arbitrary primordial dilution to manufacture any N/C. Their isotope
predictions are published model predictions; this spectrum measures none.

All four selected rotating benchmarks also conflict with the coadd fixed-k=1
conditional ionic profiles. All four become compatible in every cell of the
native generic-point empirical-noise family (profile deviance ranges 1.83–3.56,
below 3.841). The nominal-LSF empirical family retains threshold conflicts in
some cells for three benchmarks. This treatment sensitivity prevents a robust
model exclusion. Fixed rotating ratios and SMS upper ceilings describe different
predictions; lower profile deviances do not establish a preference for SMS.

## Formation and cosmology remain separately conditional

The previous Planck18 clocks are replayed without attaching unsupported ages to
the SMS yields. The transferred 204-Myr WR history exceeds a z=20-onset budget
by 99.04 Myr and requires onset z≥34.96. The 103-Myr example fits that budget
by only 1.96 Myr. A clock-feasible history is not a chemical fit; a luminous
young burst is not the age of every stellar generation. No complete
yield/retention/star-formation history likelihood is available.

The VMS and WR histories are loaded from the versioned benchmarks with primary
source URLs and locations in every clock record. The 40/150-Myr AGB endpoints
are explicitly illustrative delay assumptions carried by that history
benchmark, not a newly calibrated stellar-lifetime grid or an AGB exclusion.

There is no selected-mechanism posterior, calibrated abundance exclusion,
galaxy-formation anomaly or cosmological inference. The next discriminators
are calibrated ionic stage fractions and C IV transfer; source-specific
spectral reduction and covariance; separated density/O/He diagnostics with
hydrogen lines; emitting gas and differential retention; full versioned stellar
yield histories; and a completeness-controlled population for cosmology.

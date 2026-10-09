# Chemistry requirements under two resolution treatments

This further experiment compares the merged first-round illuminated-slit fit with
the generic point-source resolution fit. The elemental targets, yield table,
solar reference, and mixing calculations remain fixed. No new N/C measurement or
stellar-population exclusion follows: the spectrum still constrains the product
`Q_eff × number(N/C)`, without a calibrated emissivity/ionization map for `Q_eff`.

## Pinned inputs and reproduction

- Illuminated input: `research_output/mom_z14_line_sensitivity.json`, merged in
  PR #18; SHA256 `769f494a493fd5295dfaf8a02c47e8a7a0b90686c367da8369e9b26ef7a73a55`.
- Point-source input: `research_output/mom_z14_point_resolution.json` at spectroscopy
  commit `08d76759aebacc03164117ff941282fed195e50b`; SHA256
  `97518c1f0992b49970120b3e563ad2387cbf306f384329185292d771ef51827d`.
- Both fit the identical archived pixel-spectrum bytes, SHA256
  `42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1`.
- Enrichment benchmarks retain their original SHA256
  `8d80da92f18526b361f29244d9c57c1cdfdc82e240a2e334a1595cb29d096930`.
  All bracket N/C targets use the MoM paper's solar `log(N/C)=-0.60`, including the
  rotating-star raw N/O and C/O predictions. For example, the selected EMP
  top-heavy remnant model is `[N/C]=+0.73`, not its author's `+0.76` on a different
  solar reference. These rounded benchmark endpoints are not hard physical bounds.

```bash
python -m discovery.chemistry_identifiability \
  --comparison-report research_output/mom_z14_point_resolution.json \
  --output research_output/chemistry_resolution_comparison.json
pytest tests/test_enrichment_constraints.py tests/test_chemistry_identifiability.py
```

If the point-source report has subsequently changed, recover the exact input
first with `git show 08d76759:research_output/mom_z14_point_resolution.json` and pass
that file to `--comparison-report`. The original
`research_output/chemistry_identifiability.json` is preserved and a regression
test checks that the legacy input still reproduces it exactly.

The separate scenario families contain 31 illuminated and 29 point-source fits.
They share data and cannot supply independent likelihoods. Their scenario ranges
are sensitivities, not confidence intervals or samples from a posterior. Each
nominal scenario is the first stored 1D fit at fixed published redshift, diagonal
pixel covariance, and that family's resolution prescription. The point-source
Gaussian has R=122–182 at the five line groups, versus R=61–98 for the earlier
illuminated Gaussian. It is not the full published UNITE runtime or a measured
source-specific LSF. The published MoM analysis already included instrumental
resolution; this experiment does not establish an omission in that analysis.

## Measured ratios and conditional nuisance requirements

The covariance propagation uses the full fitted line-flux covariance, including
covariance between the nitrogen and carbon sums. Formal 95% Fieller sets below
condition on each fit's nuisance choices and Gaussian error model. Signed values
are retained; no positive-parameter posterior is constructed.

| Quantity | Illuminated fit | Generic point-source fit |
| --- | ---: | ---: |
| `(NIV+NIII)/(CIV+CIII)` | 1.03944 | 1.05018 |
| Formal conditional 95% Fieller set | [0.44829, 2.15895] | [0.50178, 2.04723] |
| Separate scenario point range | [0.64227, 1.33634] | [0.61924, 1.41257] |
| Q required for fixed Cue median `[N/C]=0.90` | 0.52096 | 0.52634 |
| Formal conditional 95% set for that Q | [0.22468, 1.08204] | [0.25149, 1.02604] |
| Separate scenario point range for that Q | [0.32190, 0.66976] | [0.31035, 0.70796] |
| Q required for separate ionic case `[N/C]=1.30` | 0.20740 | 0.20954 |
| Q required for separate ionic case `[N/C]=1.70` | 0.08257 | 0.08342 |
| Q required for EMP rotating top-heavy remnant `[N/C]=0.73` | 0.77055 | 0.77851 |

At every fixed elemental target, the nominal required Q increases by 1.033%.
The lower and upper conditional 95% endpoints change by +11.932% and −5.175%,
respectively. Thus the summed ratio's central value is comparatively stable here,
while its covariance and ion-stage allocation are resolution-sensitive. The
separate ionic `[N/C]=1.3–1.7` values are published temperature-model cases, not a
95% interval or a replacement for the Cue marginal inference.

The nominal NIV/CIV ratio changes from 1.442 to 1.279 and NIII/CIII from 0.497 to
0.699. NIII/CIII's conditional 95% set still crosses zero in both cases
([-0.271, 1.827] and [-0.096, 2.478]). The point-source HeII/OIII-blend/CIII set
also crosses zero ([-0.034, 3.906]). These diagnostics need an atomic forward map,
higher resolution, and unblended helium/oxygen constraints before they identify
ion fractions or chemical enrichment channels.

## Does resolution change a rejection?

For a specified, unmeasured positive Q, dividing the conditional line-ratio set
by Q creates a mathematical abundance set. Under equal retention and mixing
with lower-N/C gas, a particular SMS yield provides a ceiling. The assumed-Q
threshold below which the entire conditional 95% set exceeds that ceiling is:

| Discrete SMS initial mass (Msun) | Illuminated threshold Q | Point-source threshold Q |
| --- | ---: | ---: |
| 1000 | 0.30488 | 0.34126 |
| 10000 | 0.01249 | 0.01398 |
| 50000 | 0.01110 | 0.01243 |
| 100000 | 0.03617 | 0.04049 |

The thresholds move by 11.932%. For example, at an arbitrarily fixed Q=0.32 the
point-source nominal conditional set lies above the 1000-Msun model's ceiling,
whereas the illuminated set overlaps it. Q=0.32 is an illustrative assumption,
not a prediction or estimate. This resolution sensitivity changes a conditional
algebraic test; it does not exclude that stellar population. There is no atomic
grid, inferred Q, calibrated yield uncertainty, or mechanism likelihood here.
The machine-readable list of identified mechanism exclusions is empty.

Joint yield/mixing checks at the published fixed targets are **exactly identical**
between the resolution families. For the Cue median, the numbers of cases passing
the chosen O/H+C/O marginal endpoint rectangle remain 0/36, 24/36, 12/36, and
12/36 for the four SMS masses. For the upper ionic case, they remain 0/36, 0/36,
12/36, and 0/36. These are deterministic grid-choice counts, not probabilities or
statistical exclusions. The 100000-Msun ejecta ceiling of 1.69317 dex misses the
rounded 1.70 target by only 0.00683 dex; yield systematics prevent interpreting
that difference as a robust population rejection. Failure of the Cartesian
marginal rectangle rejects that stated rectangle scenario only, not the model
without its joint posterior and yield uncertainties.

The most useful next experiment is an emissivity/ionization forward grid that
predicts the nitrogen and carbon ion stages, helium/oxygen blend, and hydrogen
lines jointly for the same enrichment and gas scenarios. It should then be fit
to calibrated alternative extractions with source LSF and correlated noise.
Full trace-weighted native quality masks and independent nod fits remain needed
to establish which spectral bins control those diagnostics. A resolution change
alone does not remove the chemistry non-identifiability.

## Validation

The combined enrichment and chemistry tests pass (28 tests), including original
snapshot preservation, full covariance propagation, separate resolution-family
handling, identical fixed-target mixing checks, and rejection of mismatched
pixel inputs. Ruff passes for the two changed Python files. An unrestricted
repository-wide Ruff run reports inherited lint failures outside this change;
those older style issues do not alter the scientific comparison.

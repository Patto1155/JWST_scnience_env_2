# Independent complete composition-grid likelihood review

Question: does the complete20-model thermal pilot couple to the fresh RATE v3 measurement likelihood without a stale noise scale, missing donor response, incomplete multiplet or held-out selection leak? Competing predictions are agreement of an independent direct fourteen-component constrained GLS with every reported total likelihood and training-only prediction, versus numerical disagreement exposing a coupling or selection error. Expected information gain is certification or rejection of the full bridge across its environmental controls; it does not validate a population posterior or empirical source calibration.

The review is separate from literature's model author and from the raw thermal-model validator. It starts from the earlier independently validated paired bridge `03f2687`, preserving that contract. A new standalone oracle integrates literal fourteen-component Gaussian CDFs using `erf`, constructs source-column wavelength grids, contracts actual CAL profiles/pathloss with RATE calibration gains and signed extraction weights, assembles full noise covariance directly from measured blocks/kernel/fresh scale, and solves direct Gram GLS. It calls none of the author's prediction, fitting, normalization or held-out functions. Covariance precision is reused only to bound computation; an independent test verifies equality with uncached GLS. Normalization is constrained nonnegative with the continuum refitted at the boundary. The historical pair regression passes48 fits and six predictions in7.48s; three invariant tests and Ruff pass.

Before full outcomes, fix the expected20 distinct models in ten ordinary/enhanced environmental pairs,29 finite nonnegative line responses, eight separately reported original/DUMMY×nominal/generic-point×formal/empirical alternatives, three attenuation screens,480 total fitted records and six held-out predictions. Independently compare every five-line covariance, total constrained native chi-square, normalization and component-summed response. Within each alternative, independently identify ordinary/enhanced/global minima and compare profile differences. Recompute held-out model/screen choice from training exposures alone; independently integrate the truncated-amplitude moments and full predictive covariance, profiling test continuum. The common noise transport remains conditional on pooled off-source controls; it is not trained solely on each training subset.

Budget: zero downloads, no new Cloudy runs, at most180s numerical review. Stop and reject approval on any changed input hash, missing model partner, duplicate model/screen record, incomplete line response, native discrepancy exceeding2e-6 in recorded units, wrong held-out selection, or computational-cap failure. Model counts are validation dimensions only. No grid-count probability, selected-minimum fixed-degree-of-freedom p-value or empirical likelihood coverage is computed. Scalar source-column response, unknown source LSF/absolute wavelength, ionizing spectrum, attenuation, C IV transfer and model prior choice remain assumptions. Actual raw thermal convergence and atomic provenance are validated separately.

The complete20 artifact must be immutable before numerical review. Final results and reviewed hashes are added only after that freeze. Reproduction uses `discovery/research2_cloudy_grid_rate_review.py` with the complete artifact, RATE receipt and pinned native CAL directory.

## Immutable full20 results

The reviewed author freeze is `a49e7f3`, artifact `mom_cloudy_pilot20_rate_v3.json`,2,221,190bytes/SHA256`7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759`. Working bytes exactly equal the artifact stored in that commit. The independent actual-nine-CAL gain/profile contraction and full480-record likelihood review completed in14.862s, within the180s cap, with zero acquisitions or new thermal runs.

Maximum absolute discrepancies are1.924e-10 in five-line flux,3.174e-9 in flux covariance,7.743e-11 in constrained total chi-square,9.660e-11 in normalization and zero in physical component sums. The independently constructed gain coupling agrees to4.45e-16. All six training-only model/screen selections agree; independent truncated means/variances/intervals and full-covariance predictive quadratics differ by at most3.802e-10. All480 records, ten paired environments, eight alternatives and family minima pass. Three invariant tests and Ruff pass; the numerical bridge is independently approved. Raw thermal convergence, complete release provenance and all29 saved line identities are the separate thermal review's responsibility.

| Conditional alternative | Ordinary-family minimum chi-square | Enhanced-family minimum chi-square | Ordinary minus enhanced |
|---|---:|---:|---:|
| Original, nominal, formal RATE | 787.825 | 784.883 | 2.943 |
| Original, generic point, formal RATE | 785.197 | 782.224 | 2.974 |
| Original, nominal, fresh empirical | 556.459 | 554.527 | 1.931 |
| Original, generic point, fresh empirical | 554.534 | 552.552 | 1.982 |
| DUMMY, nominal, formal RATE | 786.530 | 782.547 | 3.984 |
| DUMMY, generic point, formal RATE | 785.266 | 780.667 | 4.599 |
| DUMMY, nominal, fresh empirical | 555.591 | 552.940 | 2.651 |
| DUMMY, generic point, fresh empirical | 554.687 | 551.547 | 3.140 |

These are descriptive profile differences across finite model families, not odds, calibrated likelihood-ratio confidence or selected-minimum fixed-dof p-values. The ordinary original/generic-point/empirical minimum uses logU=-1 and blackbody60,000K; the enhanced minimum uses logU=-2 and blackbody100,000K. Their different environmental choices prevent attributing the family difference uniquely to nitrogen. DUMMY remains a sensitivity calculation. The change from formal-only to empirical noise is much larger than the ordinary/enhanced profile separation; uncertainty in transporting off-source noise to source pixels remains material.

Held-out ordinary versus enhanced predictive quadratics are188.277/186.470,209.011/212.121 and157.503/154.851 for groups03,05,07. Enhancement improves two held-out groups and worsens one. No consistent independent-group preference is established; pooled controls and fixed source calibration limit the validation further. No selected model is assigned a posterior probability. The broader complete-thermal pilot makes the ordinary-composition explanation explicitly testable and does not reject it under the fresh empirical original-wavelength measurement assumptions. It establishes no elemental abundance, polluter, new source or cosmological conclusion.

Executable reproduction, after the reviewed author artifact is integrated:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_cloudy_grid_rate_review \
  --artifact research_output/mom_cloudy_pilot20_rate_v3.json \
  --rate-report research_output/mom_native_rate_noise.json \
  --native-dir /path/to/pinned-nine-CALs
python -m pytest -q tests/test_cloudy_grid_rate_review.py
```

The oracle reads actual pinned CAL pathloss/profile inputs but replays RATE noise from the independently validated compact covariance receipt. This is actual-CAL coupling plus numerical RATE likelihood replay, not another raw RATE reproduction. Next priorities are empirically measured source LSF/common centroid calibration and independent ion-stage/density diagnostics, rather than expanding a generic grid solely to count members.

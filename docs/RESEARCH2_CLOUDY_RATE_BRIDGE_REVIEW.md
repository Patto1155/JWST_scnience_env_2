# Independent composition-aware RATE bridge review

Ownership: spectroscopy reviews the Cloudy author's bridge; PSF/noise separately validated the underlying RATE measurement contract. Target author commit is6d6fd5e. No new data, model run or candidate selection is performed.

Question: do complete physical component predictions pass through the gain-corrected signed operator and fresh RATE covariance, with exactly one donor-noise propagation and freshly estimated off-source normalization? A direct constrained continuum-plus-physical-spectrum regression should equal the author's two-stage group fit plus nonnegative common normalization. Held-out model selection and predictions should use fresh v3 measurements and covariance.

The independent tool builds all14 line-component CDFs from declared vacuum wavelengths and complete saved Cloudy intrinsic intensities, applies attenuation to each component, builds group totals, and directly regresses continuum plus their total spectrum using Gram GLS. It calls none of the author's prediction, group fitting, normalization or held-out functions. The gain coupling is reconstructed from original CAL point-pathloss arrays, independent erf-integrated source profiles, frozen spatial operators and actual RATE calibration gains. All CAL pins and the fresh noise compact receipt are verified. Source covariance itself was independently approved inffb3254.

Results: all48 component-aware native fits across eight separate resolution/wavelength/noise alternatives pass. Maximum flux difference is1.86e-10, covariance3.14e-9, direct constrained total chi-square3.86e-11, nonnegative normalization8.79e-11. Physical summed predictions agree exactly. Reconstructed gain coupling differs by4.45e-16. Formal noise uses scale1; empirical noise uses the freshly re-estimated1.427615919211 with its fresh row/column covariance. The historical2.2206 scale is absent from these primary alternatives.

All six held-out predictions pass: selected training model and attenuation match, independent truncated-Gaussian moments and intervals match, and a full predictive covariance regression reproduces the author's projected rank-one quadratic within4.37e-10. Test source amplitudes are not retrained. These are conditional predictions under the frozen covariance estimated from all off-source controls, not a fully independent covariance-calibration test. Model selection and amplitude uncertainty do not bound common calibration errors or assign posterior model probabilities.

The primary original-wavelength/generic-point empirical ordinary-composition pilot is statistically adequate only under its declared stationary noise and source-response assumptions. A single environmental pair does not span the physical density/metallicity/ionizing-spectrum degeneracies. DUMMY remains a wavelength sensitivity experiment. The bridge uses the scalar source-column wavelength convention; full row response, unmeasured source-specific LSF, thermal-model alternatives, ionizing spectrum and C IV transfer remain material. This review approves numerical coupling, not elemental N/C, a stellar polluter, empirical interval coverage or cosmology.

Executable independent review:

```bash
OPENBLAS_NUM_THREADS=1 python -m discovery.research2_cloudy_rate_bridge_review \
  --artifact research_output/mom_cloudy_focused_pair_rate_v3.json \
  --rate-report research_output/mom_native_rate_noise.json \
  --native-dir /path/to/pinned-nine-CALs
```

The JSON receipt pins the author artifact and underlying noise inputs. Historical positive-only and demixed-noise controls remain separately versioned and are not pooled with the eight fresh v3 alternatives.

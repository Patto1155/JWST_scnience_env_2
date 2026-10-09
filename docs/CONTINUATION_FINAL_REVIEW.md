# Independent review of actual continuation experiments

9 October 2026. This addendum preserves the first two reviewer reports. The
checks below reuse observed photons, pinned physical inputs and explicit model
assumptions. Alternate matrix solvers are validation, not new observations.

| Reviewed change | Independent check | Outcome |
|---|---|---|
| Spatial covariance `4e5fa23` | Nine actual CAL products; latent pixel matrices, explicit nod mixing and extraction | Exact actual science replay; transported blocks agree to 6.22e-12 of scale |
| Native chemistry `c0aab158` | Exact atomic/Cue regeneration; whitened NNLS for all 2,025 models in each four native families | Best chi² errors ≤5.6e-16; four-group threshold counts 124/145/583/672 |
| Atmosphere `61f8f58`, corrected `055269f` | Independent actual author-table parse; all-row NNLS and precision-matrix held-band residuals | 1,052 rows; 16 best fits agree within 1e-10 chi² |
| Persistent patch `0214af31`, corrected `f2eed690` | Four actual images; independent SVD/background/cluster-influence algebra | Exact replay; six quantities across 104 fits agree within 5.46e-12 nJy |
| Observed-profile injections `bbee1c1` | Actual full 2,436 insertion replay, distinct tuples/sites, paired losses and radial-annulus boundary | Exact compact result and canonical full-table hash |

The spatial oracle independently demixes diagonal variances using the analytic
three-nod inverse and exhaustive nonnegative active sets. It constructs a
latent row covariance for every raw nod, applies an explicit Kronecker nod
mixing matrix, adds the independent positive remainder, then applies source
extraction matrices. This differs from the production pairwise contraction and
NNLS solver. Forty-three selected pixels require reconciliation. The resulting
point scenario retains line-flux ratio 0.793061 and conditional 95% Fieller set
[-0.005984,2.883561], admitting zero nitrogen. Stationary separable transport,
overlapping off-trace pairs, unknown source calibration and shared references
remain assumptions. The original frozen reduction is unchanged.

The native ionic map and Cue outputs exactly reproduce their saved JSONs and
input SHA256 `88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec`.
The Cue oracle uses the marginal four-group covariance and a different
whitened constrained optimizer. N IV] is absent from that versioned emulator,
not assigned zero. Sparse threshold sets are not confidence regions. The
previous ionic/yield oracle independently checked the complete five-group
projection and Fieller roots. Elemental stage corrections remain unmeasured.

The independent atmosphere parser counts 273 + 389 + 351 + 39 = **1,052** rows
inside Teff=200–2400 K and log(g)=3.25–5.5. Review corrected an earlier prose
count of 1,053; a 2401-K row is outside this explicit guard. The measured fluxes
and numerical outputs were already correct. Header-derived JWST identities,
log10(mJy at 10 pc) units and rejected mislabeled C/O=1.5 table are preserved.
The 5%/15% assumed-floor best chi² values 171.49266/49.38335 and held F277W
prediction about 1.35 nJy versus measured 9.74 nJy expose the finite cloudless
grid's discrepancy. They neither identify the source nor exclude all cool
atmospheres. Conditional distance and follow-up motion predictions remain
explicitly dependent on an inadequate model.

The patch oracle reuses actual geometry/calibration and transported finite PSFs
but replaces the normal-equation fit with an SVD pseudoinverse and replaces the
cluster sandwich's meat matrix with summed coefficient influences. The blue
joint point parameter stays 31.33–44.57 nJy, while the source-excluded background
aperture spans **-12.08–92.15 nJy**. This rejects a background-independent reading
of the old negative aperture residual. It does not calibrate a blue detection
or dropout identity. Large red residual objectives invalidate precise physical
point fluxes. Review corrected a negligible F200W table rounding discrepancy;
the saved code and actual science outputs were unchanged.

Observed-profile injection review found a real geometry defect: the nominal
0.7–1.0-arcsec template-sky annulus originally used only an inner radial bound
inside a square cutout. Corners outside 1.0 arcsec contaminated its estimate.
The corrected change adds an outer bound, a corner counterexample, and reruns
all 2,436 trials. Full canonical table SHA256 is
`6b47b731d8afdd4563534b5cbc40d50b85190671bb28986a8f0ab2841b15ed49`.
The eight-pixel detector has 149 paired recovery losses and no gains when
increasing prescribed brightness. The central blended case still loses recovery
from 9/29 to 3/29 sites. This illustrates nonmonotonic segmentation on real
structure, not survey completeness or transferred classifier validation.

## Reproduce reviewer artifacts

After science dependencies are merged, run in the repository root with the
locked environment. Raw data remain external; original reports provide their
bounded acquisition recipes.

```bash
python -m discovery.continuation_final_review spatial \
  --native-dir /cache/literature-r3 \
  --baseline research_output/mom_native_reduction.json \
  --comparison research_output/mom_native_spatial_covariance.json \
  --output /tmp/continuation_spatial_review.json
python -m discovery.continuation_final_review atmosphere \
  --archive /cache/sonora_bobcat_photometry.tar.gz \
  --manifest data_sources/survivor_atmosphere/manifest.json \
  --comparison research_output/survivor_atmosphere.json \
  --output /tmp/continuation_atmosphere_review.json
python -m discovery.continuation_final_review patch \
  --original-dir /cache/original_round3 --repeat-dir /cache/smacs-repeat \
  --short-psf /cache/pinned-short-psfs --long-psf data_sources/pilot \
  --comparison research_output/smacs1043_patch_diagnostics.json \
  --output /tmp/continuation_patch_review.json
python -m discovery.covariant_model_review cue \
  --model-input /cache/cue-v0.1.zip \
  --spectrum research_output/mom_native_reduction.json \
  --comparison research_output/mom_native_cue_grid_fit.json \
  --output /tmp/continuation_native_cue_review.json
```

The patch command also writes a temporary science replay/PNG beside its receipt
so actual input/geometry behavior can be compared in full. Its interception of
fit arrays is scoped to the audit and restored even on failure. Four independent
controls check unequal-variance active sets against SciPy NNLS, a nonlocal
row-covariance counterexample, invalid covariance rejection, and signed source
recovery on a synthetic quadratic background.

Five compact reviewer receipts pin every comparison input. Final physical
inference still requires source-specific spectral calibration, model-coupled
multiplet/He-O/line-transfer fits and N IV]-inclusive photoionization; independent
epoch imaging and joint neighbour modeling; age-dependent stellar histories,
yield/retention/ionization uncertainties and calibrated population selection.
No discovery, enrichment mechanism or cosmology is certified by this review.

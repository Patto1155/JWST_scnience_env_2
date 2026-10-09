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

## Physical multiplet and assembly round

The next two frozen changes, physical multiplets `08303681` and formation
`ed63ca5`, were independently reviewed after those earlier checks. The actual
PyNeb1.1.32 component regeneration reproduces SHA256
`cbd151a8274979f9378b0ce485f23793ca77ccc9eb1df8eae391012691d3fb8e` byte-for-byte.
Another full-native bin-integrated design and normal-equation solver checks all
112 fresh flux/covariance fits; maximum flux disagreement is 2.83e-10 in stated
flux units, covariance difference is 1.81e-11 of scale, and ionic-ratio
difference is 7.41e-11. Each atomic projection and polynomial Fieller interval
uses its own cell's refitted covariance. Equal He/O mixture, single-line N IV],
optically thin C IV, fixed source geometry and the original four noise scenarios
are accurately distinguished from independently measured physics. Those fits
do not combine the separate spatial-covariance sensitivity with this new
template correction. A full N IV]1483+1486 contract is the next version, since
1483 emissivity is not negligible; v1 must remain reproducible as scoped.

The formation generator is byte-identical on independent replay. Numerical
quadrature checks all 720 histories, their nested 5/50-Myr means and half-mass
times, with maximum surviving-mass discrepancy 2.1e-15 relative. Eighty inverse
histories/asymptotic ceilings and 216 closed-parcel baryon budgets independently
agree. The primary [paper, Table 1 and §3.2.2](https://arxiv.org/html/2505.11263v2)
and [official Prospector FAQ](https://prospect.readthedocs.io/en/stable/faq.html)
were inspected: the paper does not resolve its mass conversion, while the
software defaults to formed mass. Both quoted-mass interpretations are retained.
The rising formed-mass histories give a conditional conventional counterexample
inside published individual marginal ranges; this is not a joint SED fit or a
cosmological likelihood. Constant effective return, uniformly interleaved duty,
closed-parcel gas and hypothetical polluted mass remain explicit assumptions.

```bash
python -m discovery.continuation_physical_review multiplet \
  --output /tmp/continuation_multiplet_review.json
python -m discovery.continuation_physical_review formation \
  --output /tmp/continuation_formation_review.json
```

These two reviewer receipts pin the exact frozen science reports. The alternate
solver fails closed for missing scenarios, bad input receipts, nonfinite or
misordered likelihoods and incomplete fits. Two additional synthetic
counterexamples reject substituting the active-duration mean for a nested
50-Myr mean and substituting a last bright phase for half-mass time.

## Full N IV doublet, wavelength and yield follow-ups

The version2 N IV contract `415e91d5` was independently regenerated from the
actual pinned PyNeb1.1.32 atom: both new grids are byte-identical. At the
reference cell, the distinct1483(4→1)/1486(3→1) transitions have emissivity
ratio1.480924; the total response is2.480924 times the single-line response.
Fresh normalized-doublet fits precede application of that response. The actual
112-fit CLI result is byte-identical to frozen report SHA256
`446c1f7a35ed8c8e272ba277576088f7a4dbbd6d75dcceb2dd6c1767b2891b63`.
The independent full-grid normal-equation check of112 fits gives flux
disagreement2.84e-10, covariance disagreement1.77e-11 of scale and ionic-ratio
disagreement3.36e-11. Signed polynomial Fieller roots match every cell. The
point empirical reference2.7504[−0.5064,9.5916] and all28 zero-inclusive cells
weaken the earlier conditional ionic enhancement. No elemental stage fraction,
source-specific LSF or He/O/C IV transfer is calibrated by adding the doublet.
The older single-line result and its reviewer receipt remain unchanged.

The corrected wavelength experiment `2f714d8` is approved as a **DUMMY-reference
sensitivity**, not empirical calibration. All nine actual CALs regenerate the
full science/provenance JSON and NPZ byte-for-byte (only output filenames differ).
Another actual ASDF reader verifies the reference's meter/source-fraction axes,
21×21 lookup table, variance metadata, DUMMY pedigree and internal `_0002`
filename. Its Tabular2D evaluator and an independently written endpoint-linear
mapping reproduce the corrected native wavelength grids within1.78e-15µm.
The independently opened nine raw GWCS models have no wavecorr frame; their
half-pixel dispersion derivatives match the compact arrays exactly. Stored
float32 wavelengths differ by at most2.3842e-7µm. Target EXTENDED classification
and WAVECOR=False are preserved facts: the point-source alternative changes a
classification hypothesis. Twelve full-grid normal-equation GLS fits match
fluxes within2.90e-10, covariance within1.82e-11 of scale and chi² within1.33e-10.
Planned source position, toy correction, frozen amplitude/noise/pathloss and
generic R remain assumptions. A positive lower endpoint under this toy model
does not justify selecting a detection model. In the legacy generic-point
row+column comparison, chi² increases1.029; the composed response depends on
resolution.

The versioned yield bridge `4d25697` regenerates its entire JSON exactly.
Independent operators project224 fresh five-group fits to their own full2×2
ionic covariances, with the matched single-line or total-doublet response.
Benchmark mass yields are independently converted to number ratios before
profiling. Whitened SciPy NNLS agrees for all5,376 cones and unrestricted
positive quadrants within1.43e-14 in deviance; every deterministic matched
threshold count agrees. Version2 point empirical profiles have0/28 cells above
the illustrative3.841 reference for every one of eight selected benchmarks and
all three fixed k values. The discrete models, fixed k and equal retention are
conditional assumptions; this is not a mechanism probability or exclusion.

```bash
python -m discovery.continuation_physical_review niv_doublet \
  --output /tmp/continuation_niv_doublet_review.json
# ASDF/GWCS extras from the experiment receipt are required for the actual audit.
python -m discovery.continuation_wavecorr_review --root . \
  --native-dir /path/to/pinned/nine-CAL-cache \
  --output /tmp/continuation_wavecorr_review.json
python -m discovery.continuation_yield_version_review --root . \
  --output /tmp/continuation_niv_yield_review.json
```

New controls reject unknown atomic versions, endpoint clamping/noninvertible
wavelength maps, shortened-bin construction across masked columns, endpoint-only
mixture fitting, and using a signed unrestricted Gaussian as the positive-quadrant
reference. The consolidated report was also reviewed for inference claims:
43 reconciliations refer to selected UV pixels, and independently computed
annulus alternatives reuse the same254 photons. Reproducible numerical agreement
does not remove those observational/model limitations.

## Final composed spectral round

Frozen change `ab4dabd4` is approved at report SHA256
`fd14eb0028016c7c66c09cdae74a6474416e11c6a29003103e274887ab0fdc50`.
It executes336 fresh physical-doublet likelihoods:28 cells × two generic R
families × three fixed covariance families × original/toy wavelength grids.
The independent full-native bin integration and normal equations reproduce
all336 flux vectors and full5×5 covariances (maximum differences2.86e-10 in
flux units and1.79e-11 of covariance scale). Each cell's independent atomic
projection and signed Fieller roots agree, with ionic-point differences3.36e-11.
The actual production CLI agrees in exact structure/lineage and across19,706
floating values at1e-12 relative/absolute tolerance. Its reference-cell figure
and literal reproduction commands were inspected; a test filename typo was
corrected before freeze.

With row+column empirical transport and generic point R, the reference original
grid gives2.7535[−0.5058,9.5970], and the toy prediction3.7236[0.1077,14.5265].
Every original empirical cell admits the0.2512 ambient ionic reference. Toy
families admit it in16/28 nominal and18/28 point cells. These deterministic
counts and signed intervals retain the model contrast; it would be wrong to
say every alternative admits zero, or to select an instrumental hypothesis
from a positive lower endpoint. Equal stage fractions would be needed to
interpret that ionic reference as elemental solar N/C. All alternatives reuse
the same observations, amplitudes and frozen source-noise models. No pooling,
calibrated wavelength/LSF, elemental inference or mechanism odds follows.

```bash
python -m discovery.continuation_composed_review --root . \
  --output /tmp/continuation_composed_review.json
```

The new normal-solver counterexample admits a valid covariance with exact zero
off-diagonals and a signed negative line, while rejecting nonfinite covariance.
All20 focused reviewer controls pass in the locked research runtime, with Ruff
and Mypy passing for the four changed/new numerical modules. Earlier reviewer
and science output bytes remain untouched. Consolidated-report feedback now
qualifies zero-inclusive28-cell counts by the original-wavelength family rather
than extending them to the DUMMY alternatives.

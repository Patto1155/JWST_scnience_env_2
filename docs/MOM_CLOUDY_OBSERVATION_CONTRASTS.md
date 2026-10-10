# Complete-model UV observation contrasts

The complete20-model thermal pilot now supports a specific observing priority:
**N III with a C III anchor separates the finite ordinary/+1dex alternatives far
more strongly than N IV+C III or He/O+C III alone.** This is a conditional
model-to-model observing forecast, not a new abundance measurement or a guarantee
of feasible exposure time. The additional N V and C II ratio ranges overlap.

The predeclared four bundles are N IV+C III, N III+C III, He II/O III+C III and
all fourteen fitted UV components. Each separate G235M or G235H nominal response
uses intrinsic FWHM0/300/1,000km/s, with independently retained intrinsic and
emergent thermal-model responses:48 conditional cases. Every case compares the
same ten ordinary and ten nitrogen-enhanced environmental controls, with the
existing attenuation values0/0.5/1mag profiled and a free nonnegative total
normalization. No physical model, attenuation grid or acquisition is added.
The execution cap is60seconds; an incomplete, unmerged or unvalidated thermal
input stops dependent analysis.

## What ordinary and enhanced mean

Ordinary means declared gas-phase log(N/C)=-0.60 **at declared log(C/O)=-0.37**,
with GASS10 base metals and custom C/N/O overrides. It is not the unmodified
solar element pattern. Enhanced changes nitrogen alone by+1dex and independently
recomputes thermal balance. Identical input-environment pairs control that
change; cross-environment comparisons expose degeneracy among the frozen
alternatives. Exact line strengths and component ratios must come from each
complete model. Nitrogen intensities must not be multiplied by ten or transferred
between independently recalculated thermal models. Normalizing to C III versus
He/O can change the apparent response factor because those anchors also respond
to thermal balance. These are different diagnostics, not conflicting results.

## Conditional SNR does not establish observing feasibility

The shape metric profiles the ordinary alternative's nonnegative total amplitude.
It assumes white constant variance per unit observed wavelength, known continuum,
centroid, width and geometry. Reported SNR is the matched-template SNR of the
*enhanced truth* in that particular bundle/mode. An expected squared separation9
is an illustrative conditional distance, not a calibrated rejection probability.
Each intrinsic/emergent response contract and instrument mode remains separate.
The hardest cross-environment pair is a finite sensitivity summary, not a
population prior or a posterior bound. Additional astrophysical model families
could be harder to distinguish.

The merged [local-identifiability experiment](RESEARCH2_LOCAL_IDENTIFIABILITY.md)
constructs exact Gaussian intrinsic-width/source-LSF counterexamples and
assigned-centroid/redshift calibration counterexamples. Consequently these
forecasts require **measured source LSF and wavelength zero point** before any
intrinsic width or component-density interpretation. Higher nominal resolution
alone does not provide that calibration. Separate N IV and C III densities need
not describe the same gas. A small modeled emergent/intrinsic attenuation does
not bound MoM's C IV resonance/stellar transfer.

Nominal grating wavelength reach does not certify this source's aperture/detector
gap coverage. Archive products with zero contributing UV samples provide neither
line non-detections nor flux upper limits. In particular, any CAPERS source
SPEC/PIXTAB/X1D/S2D zero-coverage interval must be traced back to raw exposure,
shutter and trace geometry before concluding that new observing time is essential.
Existing data may resolve some missing coverage or calibration; the forecast
alone cannot settle that question.

N V and C II stage ratios are additional finite-model targets, not ionization
corrections or guaranteed measurable lines. C II uses explicit Cloudy air line
labels above2,000Å and requires vacuum conversion for exact wavelength assignment.
The optical Hβ/O III/N II wavelengths fall outside NIRSpec's nominal band; their
feasibility needs a separate instrument response and ETC calculation. No absolute
exposure time, source sensitivity, source identity, elemental N/C, stellar polluter
or cosmological odds follows from these forecasts.

## Reproduction gate

The executable requires the actual complete input SHA256 and an exact validated
merged revision; it checks both ancestry in fetched `origin/master` and the exact
artifact bytes in that revision. The actual input passed this gate at PR78 merge
`6b44032b82e550ed0f740a56830deed296b5c4e9`, with independently reviewed thermal
and RATE-likelihood artifacts. Reproduce the exact reviewed input:

```bash
python -m tools.jwst.cloudy_observation_contrasts \
  --input research_output/mom_cloudy_pilot20_rate_v3.json \
  --validated-merged-revision 6b44032b82e550ed0f740a56830deed296b5c4e9 \
  --input-sha256 7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759
python -m pytest tests/test_cloudy_observation_contrasts.py \
  tests/test_observation_design.py
```

Five original synthetic tests independently verify spectral quadrature, scalar
amplitude minimization, pure-scale nonidentifiability, exact foreground-screen
arithmetic and stage-range conventions. An additional test guards the custom
C/O contract. Synthetic fixtures test algorithms and are not Cloudy results.
The PSF specialist independently validates actual frozen model/prediction arrays
before scientific publication. The complete-input gate passed. Execution took12.170seconds, below60seconds,
with zero new acquisition and zero additional physical models. The preregistration
embedded in the result remains the historical pre-outcome plan; the separate
execution receipt records the completed state.


## Actual finite-family discrimination

All48 cases use fresh complete-model line weights. The analytic Gaussian metric
profiles each ordinary alternative's free nonnegative amplitude and both models'
existing screen choices. The closest pair is the least discriminating of100
cross-environment composition pairs; each considers9screen pairs. The ten
matched-environment pairs are retained separately. Grid counts are deterministic
sensitivity denominators, not probabilities or independent data. No native
likelihood cut or posterior weighting selects these20 models: the hardest-pair
result is conservative over the declared finite family, including models that
are not the best native-spectrum fits. It is not expected information gain
averaged over a calibrated posterior.

At nominal G235H and zero intrinsic width, the required enhanced-truth
matched-bundle SNR for the illustrative expected squared distance9 is:

| Bundle | Intrinsic response: hardest cross-environment | Emergent response: hardest cross-environment | Intrinsic: hardest matched environment |
|---|---:|---:|---:|
| N IV+C III |4,723.4|4,853.9|916.8|
| N III+C III |11.315|11.314|10.677|
| He/O+C III |1,195.0|1,194.6|1,195.0|
| Complete14-component UV |10.792|10.791|10.792|

The very large N IV and He/O numbers expose near-degenerate normalized spectral
shapes; they do not assign huge SNR to the faint nitrogen line itself. N IV's
closest intrinsic pair is enhanced40,000K/model013 with A1500=0 versus ordinary
metallicity0.5/model018 with A1500=1. Their native unattenuated N IV/C III ratios
are0.004529 and0.006449; allowed screen/normalization freedom makes these weak
N IV contributions nearly interchangeable. Even the matched40,000K composition
pair is difficult under this bundle. He/O's hardest pair is the same40,000K
ordinary/enhanced environment. These counterexamples reject the premise that
N IV strength or separated He/O alone necessarily distinguishes the entire
specified composition family.

N III+C III's hardest pair is enhanced low-U/model009 (logU=-3, A1500=1) versus
ordinary low-metallicity/model016 (Z=0.05, A1500=0). Its fractional residual shape
information is0.070302. CompleteUV's hardest pair is the matched low-U environment
models009/008 with enhanced A1500=1 versus ordinary A1500=0, information0.077279.
The limited improvement from the complete bundle identifies N III+C III as a
focused discriminator for these frozen families. This is not a general claim
that N III is always stronger, or that unknown ion fractions/stellar spectra,
multiple gas phases or source calibration have been resolved.

At intrinsic FWHM300 and1,000km/s, the G235H intrinsic N III+C III thresholds are
10.479 and9.290; completeUV gives9.997 and8.834. **Lower matched-template SNR under
broader assumed profiles does not mean less observing time.** Bundle template
norms, component overlap and known shape change, and no absolute flux or
mode-specific noise calibration is supplied. G235M's narrow corresponding
thresholds are10.707 and10.212; these cannot rank medium versus high mode in
exposure time. The measured source response and actual ETC scene remain required.

The base composition pair demonstrates why thermal recomputation and anchor
choice matter: absolute N IV changes by7.825, while C III changes by0.8850 and
He/O by0.8880. Thus N IV/C III changes by8.842 and **He/O/C III** by1.0034; a factor10
nitrogen rescaling reproduces none of this full response. Tiny model-internal
emergent/intrinsic changes do not constrain source C IV resonance transfer.

## Additional stages and what did not change

With the declared screens, intrinsic N V/C III spans0–0.002415 for ordinary and
0–0.015959 for enhanced models; the complete ordinary range overlaps. Intrinsic
C II/C III spans0.020698–0.577398 ordinary and0.020139–0.640808 enhanced, again with
the entire ordinary range overlapping. Emergent ranges are separately retained
and show the same overlap. Zero values are explicit saved model responses at
printed precision, never invented replacements for missing lines. These targets
can constrain ionization/transfer with adequate measurement, but one extra stage
ratio alone does not distinguish these whole families without other information.

No native data likelihood was refitted or multiplied by this forecast. Ordinary
composition adequacy, uncertain source LSF/wavelength, the ionic-versus-elemental
conversion, retention/mixing and polluter nonidentification retain their upstream
limits. No high-redshift source or cosmological discovery follows. The practical
next step is archive raw-trace/source-gap and calibration work, followed by a
source-specific sensitivity calculation for N III+C III and free He/O diagnostics.
That sequencing does not establish that new telescope time is essential.

The immutable [forecast](../research_output/mom_cloudy_observation_contrasts.json)
has SHA256 `a73b72229e2f20f87c14b29b84f88f50a8cb594cb0ff220eb22b93d4b8c65a29`;
[execution receipt](../research_output/mom_cloudy_observation_execution.json)
pins source/model/plan bytes and budget. Nineteen focused tests pass, including
frozen actual-input/48-case identities and independent stage replay. Separate
PSF-worker validation checks all43,200 distances,96direct wavelength quadratures,
and stage ranges: maximum information/amplitude errors6.11e-16/6.67e-16,
maximum SNR relative error7.11e-10 and direct-quadrature information error1.88e-14.
The independent review is separate from these author controls.

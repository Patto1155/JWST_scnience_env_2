# Complete20 composition-aware pilot with fresh RATE likelihood

The bounded pilot is complete:20 independently equilibrated Cloudy C23.01
models,480 separate conditional native fits and six training-only exposure-group
predictions. The +1dex nitrogen,100000K blackbody model has the lowest statistic
in each retained instrumental/noise alternative. Ordinary composition remains
conditionally adequate under empirical RATE noise. The difference does not
identify elemental N/C, a stellar polluter or a cosmological explanation.

The pre-outcome question, twenty-model specification, acquisition/compute
budgets, stopped600second attempts and declared1200second retry are preserved
in [MOM_CLOUDY_PILOT.md](MOM_CLOUDY_PILOT.md). No additional model or download
expansion followed these outcomes. The field/calibration inputs remain an
independent reduction alternative rather than an author's exact reduction.

## Frozen computation and identities

- `research_output/mom_cloudy_pilot20_rate_v3.json`:2,221,190bytes;
  SHA256 `7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759`.
- `research_output/mom_cloudy_pilot20_raw.tar.gz`:2,276,836bytes;
  SHA256 `5b36c11a1f9839e30d433198ad47ec7c69e977f476992aaa26beae853fcf4f4a`.
  Its manifest pins all140 original model files and the saved-line list.
- Full public C23.01 archive338,434,070bytes, SHA256
  `a9ad2dc037e88f552389de0e483d68f54310976dee32154ed13830882aedae0b`.
  Actual transfer352,991,151bytes includes failed prefix probes; no subsequent
  software/data acquisition was needed for this twenty-model round.
- All20 models use the same O1, retained-floating-point-traps executable,
  SHA256 `b399034fb64c0e89aaa38528a53c033b870951f3c1fb277b9b20560ddc67253f`,
  with existing SciPy LP64 OpenBLAS and `OPENBLAS_NUM_THREADS=1`.
- Wall times323.02–583.55seconds per model; summed8,779.59model-wall seconds,
  including the two explicitly reused, approved backend controls. All models
  converged after three iterations; none failed or were cancelled. Final
  allowed stops are low electron fraction or the declared1000K temperature
  floor. No adaptive-zone or atomic-accuracy convergence bound is inferred.
- The fresh RATE bridge took10.676seconds; six held-out fits took1.017seconds.
  These were below the declared120/60second budgets. Source-column wavelength
  response, gain-aware signed nod coupling and the separately pinned total
  RATE covariance are retained; row-dependent response is a distinct sensitivity.

Actual printed and every-zone C/N/O abundances, hydrogen densities,29 ordered
intrinsic and29 emergent line intensities, five component/blend sums, declared
decks and physical final stops have explicit guards. C23.01 default atomic
families are independently pinned in `mom_cloudy_atomic_provenance.json`.
Fourteen fitted UV wavelengths are vacuum; additional optical and C II
wavelength identities above2000A are AIR. All saved intensities are linear
erg s^-1 cm^-2 in Cloudy's print geometry. The measurement uses a free common
amplitude, so this is not an absolute luminosity prediction.

Independent adversarial review6f5def5 validated all20 actual thermal models
and141 preserved members, including11 final electron-fraction stops and nine
1000K-floor stops. Independent spectroscopy reviewa10543a reconstructed actual
CAL/RATE gain coupling and all14 physical component responses directly. Its
480 constrained native fits agreed within7.75e-11 in chi2, covariance within
3.18e-9, and all six training-only predictions within3.81e-10. Focused tests
and strict Ruff E/F/I passed; acquisition and runtime are recorded separately.

The background element pattern is GASS10 scaled once. Explicit gas references
are O/H=4.90e-4*Z, log(C/O)=-0.37 and ordinary log(N/C)=-0.60; the latter is
the preserved N/C convention. C/O=-0.37 is a declared gas reference, not a
claim that the entire overridden composition equals unmodified GASS10 solar.
Every nitrogen partner changes nitrogen alone and recomputes thermal balance.

## Thermal predictions and rejected rescaling

Each row compares two otherwise identical models at zero foreground screen.
Other parameters retain the declared base values. The multiplier columns
are shape changes after division by C III; the common amplitude makes these
more relevant to the likelihood than absolute nitrogen-line multipliers.

| Environmental control | Ordinary N IV/C III | +1dex N IV/C III | N IV/C III multiplier | N III/C III multiplier |
|---|---:|---:|---:|---:|
| Base: log nH3, log U-2,60000K,Z0.2 |0.01223|0.10816|8.842|9.925|
| log nH2 |0.00752|0.06838|9.099|9.819|
| log nH4 |0.01404|0.12424|8.849|9.964|
| log nH5 |0.01517|0.13371|8.812|9.968|
| log U-3 |0.00073|0.00688|9.417|9.655|
| log U-1 |0.05862|0.37061|6.322|10.227|
|40000K blackbody |0.00048|0.00453|9.531|10.015|
|100000K blackbody |0.09842|0.89730|9.117|10.045|
| Z0.05 |0.01961|0.18685|9.529|9.974|
| Z0.5 |0.00645|0.05095|7.901|9.897|

Pure nitrogen-flux rescaling is rejected as a model-construction method. In
the base pair, the absolute N IV and N III responses rise7.825/8.784 rather
than10; C III decreases to0.885 of its previous value. H+-weighted temperature
changes13462.39→13177.67K. Effective N IV/C III instead rises8.842; a22percent
absolute nitrogen-line suppression is therefore not a22percent abundance
effect after normalization. Across declared environments the N IV/C III
enhancement factor is6.322–9.531, and ordinary N IV/C III varies by over200fold.
These ranges describe finite controls, not prior distributions or uncertainty
intervals. Existing observed-stage ionic N/C is not elemental N/C.

## Conditional measurement assessment

The eight alternatives are retained separately. The table shows ordinary
family minimum minus enhanced family minimum after each family selects among
its ten environments and three foreground screens. Every global best is
model015: +1dex N,100000K blackbody, other base parameters, zero screen.
No model counts, selected-family p-values, Bayes factors or posterior odds are
computed. DUMMY wavelengths remain a sensitivity experiment.

| Wavelength | Response | Noise | Ordinary minus enhanced minimum chi2 |
|---|---|---|---:|
| Original | Nominal | Formal RATE |2.943|
| Original | Generic point | Formal RATE |2.974|
| Original | Nominal | Empirical RATE |1.931|
| Original | Generic point | Empirical RATE |1.982|
| DUMMY | Nominal | Formal RATE |3.984|
| DUMMY | Generic point | Formal RATE |4.599|
| DUMMY | Nominal | Empirical RATE |2.651|
| DUMMY | Generic point | Empirical RATE |3.140|

For original wavelengths/generic-point empirical transport, ordinary model010
(logU=-1,60000K) gives chi2=554.534; enhanced model015 gives552.552. Their
five-group shape restrictions contribute4.858 and1.022 respectively;
627 residual degrees of freedom applies only to each fixed model with its
three fitted coefficients. Ordinary adequacy reflects weak correlated
constraints, not close agreement with every central feature. Its fresh
N IV measurement is21.99±11.65 while its profiled predicted N IV is1.06
(in1e-20erg s^-1 cm^-2); the enhanced prediction is13.93 with its own fresh
projection. The full native likelihood compares the same630 measurements
rather than treating these model-dependent projections as separate evidence.
Formal transport leaves larger unexplained source residuals. Neither noise
alternative is an empirical bound on source-specific wavelength/LSF errors.

Held-out ordinary/enhanced predictive quadratics for groups03,05,07 are
188.277/186.470,209.011/212.121 and157.503/154.851, respectively, with208
continuum-projected dimensions each. Model/environment/screen choices use only
the two training groups. All select zero screen; ordinary choices are014,010,010
and enhanced choices015,015,015. Nonnegative-amplitude truncation and its
training uncertainty are propagated explicitly. Different groups favor
different ordinary environments; three groups cannot constrain a shared
instrumental systematic. These are moment-matched conditional prediction
diagnostics, not independent population samples or calibrated p-values.

## Uncertainty budget and next decisions

| Input | What is measured or checked | Remaining role in nitrogen inference |
|---|---|---|
| Photon/read variance and signed donor transport | Nine actual RATE/CAL identities, gain-aware operator and fresh total covariance | Flat-reference correlations and stationary empirical-noise transfer remain conditional |
| Nitrogen/carbon measurement | Full630-datum likelihood, physical component weights and fresh covariance per model | N IV empirical error remains about11.7 in the native flux unit; ordinary central N IV is poorly matched |
| Wavelength and instrumental response | Original/DUMMY and nominal/generic-point alternatives explicitly separated | Source-specific calibration remains unmeasured; alternatives are not a calibration posterior |
| Ionization and thermal response | Actual20 equilibria and independently varied nitrogen | Ordinary N IV/C III spans over200fold across controls; blackbody, density, geometry, fixed C/O and single-phase assumptions remain material |
| Composition nonlinearity | N IV/C III enhancement factor6.322–9.531 instead of fixed10 | A bounded pilot does not marginalize environmental priors or atomic-rate uncertainties |
| Attenuation, He/O and C IV | Three declared screens and actual separated component predictions | No measured attenuation law, component resolution or empirical C IV transfer constraint |
| Shared systematics | Three held-out RATE groups with dependent nods preserved | Agreement does not bound a shared wavelength/response/reference error |

The dominant next measurement is source-specific wavelength/LSF/pathloss and
extraction calibration, accompanied by additional independent exposure groups.
Next model-discrimination work should use this complete, independently
validated pilot to target ion stages and resolved density/He/O components;
it should follow the merged-result gate rather than expand an unweighted
scenario grid. More realistic ionizing spectra, C/O and density components
are justified only by a specific identifiable ambiguity. Stellar-yield or
cosmological inference remains blocked by abundance/retention and population
likelihood dependencies respectively.

## Executable reproduction

Numerical replay of the checked-in thermal predictions and RATE operator:

```sh
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.cloudy_pilot \
  --replay-models research_output/mom_cloudy_pilot20_rate_v3.json \
  --fit-native --held-out \
  --rate-noise-report research_output/mom_native_rate_noise.json \
  --output /tmp/cloudy20-rate-replay.json
```

Actual independent thermal reexecution, including the already pinned archive
restoration, requires the recorded compiler/backend dependencies:

```sh
python -m data_pipeline.cloudy_inputs /tmp/cloudy --build --scipy-openblas
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.cloudy_pilot \
  --cloudy-directory /tmp/cloudy \
  --executable /tmp/cloudy/c23.01/source/sys_pilot/cloudy-openblas.exe \
  --run-directory /tmp/cloudy/runs --limit 20 --workers 2 --timeout-seconds 1200 \
  --output /tmp/cloudy/models20.json
```

Numerical replay is not thermal reexecution or actual-pixel reproduction. Exact original
raw restoration uses the tar/member manifest; numerical rerun tolerances and
separate RATE/CAL acquisition/pixel commands are in `MOM_CLOUDY_PILOT.md` and
`RESEARCH2_RATE_NOISE_CONTRACT.md`. No author PIXTABs or correlated reductions
are pooled as new independent observations.

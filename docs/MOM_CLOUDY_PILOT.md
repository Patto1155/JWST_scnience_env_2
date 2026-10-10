# Complete composition-aware photoionization: declared bounded pilot

## Pre-outcome question and decision rules

The question is whether a complete N IV-inclusive, composition-aware HII-region
calculation can explain the native UV measurement with ordinary gas-phase
log(N/C)=-0.60 under the separately retained calibration/noise alternatives.
The competitor increases nitrogen alone by one dex while carbon, oxygen and
other elements stay fixed. Every composition requires a new converged thermal
and ionization solution; nitrogen flux is never rescaled from another solution.

Expected information gain is to close Cue v0.1's N IV coverage gap, replace the
unspecified stage correction with explicit physical alternatives, and identify
which spectroscopy observations discriminate otherwise similar predictions.
This pilot does not supply population odds, a polluter diagnosis, an exhaustive
ionization correction or an elemental abundance posterior.

Declared models before viewing outputs: base constant log(nH/cm^-3)=3,
logU=-2, blackbody60000K, metallicity0.2; one-axis alternatives density2/4/5,
U=-3/-1, blackbody40000/100000K, metallicity0.05/0.5. All ten environmental
controls are paired with nitrogen enhancement0/1dex: **20 full models**.
The gas pattern is GASS10 scaled in all metals, with explicit O/H=4.90e-4*Z,
log(C/O)=-0.37 and log(N/C)=-0.60+enhancement. The abundance reference is retained
as stated rather than silently adopting a different Cloudy solar default.
No grains or dust depletion are assumed. A spherical region of inner radius
10^19cm and fixed hydrogen density is illuminated by the chosen blackbody plus
the z14.44 CMB. Stop at electron fraction0.01 or temperature1000K; max3000zones
and optical-depth iteration to convergence. These are independent model
assumptions, not recovered author settings.

Acquire the complete public C23.01 archive (338,434,070bytes) within the
coordinator-granted600MiB new-selection allocation. Budget records transfer
probes separately; no paid resources. Compile with four workers, O1 and retained
floating-point traps; first-model timing must precede expansion. Each model
has a600second timeout; fail closed on missing line identities, failed
convergence or incomplete thermal solution. Expand only when the first model
passes. Stop the pilot if models fail or dominant source calibration makes a
larger grid uninformative. Independently rerun selected models and compare
component sums and thermal responses before merging.

Intrinsic UV component responses include N IV1483.32/1486.50, all five primary
N III1747–1754components, C III1906.68/1908.73, C IV1548.19/1550.77 and separate
He II1640.41/O III1660.81/1666.15. Cloudy's own five blended outputs independently
check summed responses. A foreground screen A1500=0/0.5/1mag with explicit
A(lambda)=A1500*(lambda/1500A)^-1.2 is an attenuation sensitivity; it does not
change the equilibrium computation or constitute measured dust physics.

Each actual Cloudy component ratio defines fresh native line templates and a
fresh full5x5 covariance. Profile one nonnegative common normalization and add
the group constraint quadratic to the unconstrained native residual chi2; this
is the full native likelihood after profiling the shared continuum. Do not
compare covariance determinants from different line projections, do not pool
reductions and do not interpret grid counts as probabilities. Retain original
wavelengths and DUMMY sensitivity separately, nominal versus generic point
resolution, and formal/empirical-column/empirical-row+column covariance.
Source-specific calibration remains unresolved.

## Software/input identity established before modeling

- Public release DOI: https://doi.org/10.5281/zenodo.14142065
- Publisher archive: https://data.nublado.org/cloudy_releases/c23/c23.01.tar.gz
- Publisher MD5: `73917420ab471497fa15750c751bbf1f`
- Verified SHA256: `a9ad2dc037e88f552389de0e483d68f54310976dee32154ed13830882aedae0b`
- Model methods/release: https://arxiv.org/abs/2308.06396 and
  https://arxiv.org/abs/2311.10163

The archive includes the complete atomic database and Hazy documentation.
Read the local C23.01 Hazy line-list and units contract plus the exact
`docs/LineLabels.txt` before choosing identities. The fourteen fitted UV components
below2000A have vacuum wavelengths. Cloudy's default identities above2000A
(including C II2323–2328 and the optical lines) use AIR wavelengths; future
observing targets must convert those to vacuum rather than changing the saved
Cloudy line identity.
Absolute line-list outputs are **linear**, not logarithmic, as independently
checked against `source/cddrive.cpp` and `source/save_do.cpp`; units depend on
the geometry's configured print conversion and will be confirmed on actual
outputs. The likelihood uses shape ratios and a common profiled normalization.

## First validated executable model

The corrected ordinary base model completed in460.135s,234zones and3iterations,
with no warnings or convergence failures; the final stop reached the declared
low electron fraction. Actual printed gas log(C/H)=-4.3788,
log(N/H)=-4.9788 and log(O/H)=-4.0088 agree with the declared composition.
The H+ weighted temperature is13462.39K. Independent review checked the seven
actual output-file hashes, ordered29line identities, linear intensity units,
all five component sums, every zone's composition and the convergence stop.

An earlier engineering model mistakenly applied global metallicity to an
already-scaled C/N/O pattern. Actual output validation caught this before grid
expansion. Its runtime/output are retained in the acquisition receipt, and its
line predictions have no scientific use. Corrected inputs give unscaled
reference C/N/O abundances to Cloudy, whose global `metals` command applies
the metallicity once; the actual printed and every-zone abundances are checked.

`mom_cloudy_first_model.json` contains the actual corrected thermal prediction
and its12separate signed-nod likelihood alternatives. The new source-plus-ghost
transport applies the actual signed extraction response to each nod's own
native wavelength assignment before fitting. The16KB coupling snapshot was
generated from all nine restored, hash-verified CAL pixel products. Its receipt
distinguishes later compact numerical replay from actual-pixel reproduction.
No negative nod is subtracted again and pathloss is applied once within the
forward operator. The historical positive-only response remains available only
as an explicitly requested measurement control.

For original wavelengths and the generic point response, the ordinary base
model's best screen is A1500=0. The full constrained chi2 is555.314 for627native
degrees of freedom under empirical row-plus-column covariance; its physical
five-group constraint costs7.678 relative to unconstrained line amplitudes.
Formal shared covariance gives1222.234 for the same627degrees of freedom.
This first-model result cannot reject ordinary composition under the stated
empirical noise transport, and exposes dependence on noise calibration.
It is not an abundance interval or confirmation of the blackbody spectrum.
The nitrogen-enhanced thermal partner and remaining declared controls are
running with the same600s/model stopping criterion; no conclusions are inferred
from unexecuted models.

Executable commands (locked repository environment):

```bash
python -m data_pipeline.cloudy_inputs /tmp/cloudy --build --system-lapack
python -m tools.jwst.cloudy_pilot --cloudy-directory /tmp/cloudy --executable /tmp/cloudy/c23.01/source/sys_pilot/cloudy-lapack.exe --run-directory /tmp/cloudy/runs --limit 20 --workers 4 --output /tmp/cloudy/models20.json
python -m tools.jwst.cloudy_pilot --replay-models research_output/mom_cloudy_first_model.json --fit-native --output /tmp/first-model-replay.json
python -m pytest tests/test_cloudy_pilot.py -q
```

For actual-pixel response regeneration, first restore the nine pinned CALs with
`python -m data_pipeline.mom_native_batch --spectrum data_sources/pilot/mom_z14_dja_v4.spec.fits --output /tmp/mom-native --report /tmp/native-restoration.json`, then add
`--native-directory /tmp/mom-native` to the likelihood command. Thermal
reexecution is distinct from line-array replay and requires the pinned complete
archive/build, input deck, PRNG seed319 and recorded convergence checks.

## Revised backend and focused-pair experiment declared before outcomes

After first-model PR66 merged at283b0730523fa8e3949726785dd3230d19a03f46,
the four first600s parallel controls did not produce complete final outputs.
Three additional queued controls started during executor exception unwinding
and were interrupted;12remaining controls were unstarted. No incomplete line
array is interpreted. The capped-run receipt retains identities and output hashes.
The revised scheduler cancels pending futures on failure and records exceptions.

The next question is whether an already-installed LP64 OpenBLAS backend removes
the numerical runtime blocker while preserving the complete ordinary thermal
solution, and how a newly solved nitrogen-enhanced partner differs from a simple
nitrogen-flux rescaling. Expected gain is a validated nonlinear composition
response, not a larger conditional grid. No software is downloaded. Use the
publisher LAPACK wrapper with only its three external symbol names aliased to
SciPy's existing32bit/LP64 exports. Pin the library/build hashes and force
OPENBLAS_NUM_THREADS=1. Before using a new partner, rerun the exact ordinary
input/atomic data/PRNG/convergence settings with this backend and compare all29
line outputs, gas abundances, temperatures and convergence to the validated
first model. The control cap remains600s; if it succeeds and matches, run the
ordinary/+1dex focused pair serialized or at most2workers with a newly declared
1200s maximum per model. Stop if either physics/identity check or convergence
fails. If the OpenBLAS control caps or shows no useful speed gain, retain it as an
engineering result and use the already independently validated original LP64
binary for the focused+1dex partner at1200s, comparing to its saved ordinary
model. That fallback changes no physics, input data or numerical backend.
Expand to the remaining original controls only after a successful paired
runtime/convergence preflight, preserving each failed or unexecuted alternative.

A further60s likelihood-only pilot chooses the best ordinary and enhanced
physical model using two RATE groups and predicts the third. It fixes the
original wavelength, generic point response and empirical row-plus-column
noise transport. Each test group has independently profiled continuum, while
the common line normalization is trained only on the two training groups.
Normalize the Gaussian amplitude likelihood on nonnegative amplitudes with an
explicit flat amplitude measure, and propagate its truncated mean/variance.
The resulting moment-matched predictive quadratic is a conditional diagnostic,
not a calibrated Gaussian p-value near the boundary or a physical model prior.
No model choice or amplitude refit sees the held-out group. Group agreement
cannot bound common calibration errors. Stop this pilot if runtime exceeds60s.

The completed OpenBLAS ordinary control used353.6575s wall time versus the
reference460.1354s (1.301times faster). All29intrinsic and29emergent saved
responses, all five saved ionic-weighted temperatures,234zones and3iterations
match exactly at output precision. Input bytes match exactly. Adaptive zone
profiles are not byte-identical: maximum zone-temperature difference5.8K
(relative7.024e-4) and relative depth difference8.14e-6. Equivalence is
validated for saved line responses and average temperatures; no stronger
thermal-profile identity is claimed. The executable
hash is `b399034fb64c0e89aaa38528a53c033b870951f3c1fb277b9b20560ddc67253f`;
`mom_cloudy_openblas_control.json` records this actual control, existing dynamic
library identities and the comparison. The original LP64 executable remains
the primary first-model contract. No physical conclusion changes from a runtime
improvement. The enhanced thermal partner is still pending convergence.

## Focused composition pair and conditional group predictions

The+1dex partner completed with the unchanged original LP64 executable in
378.811s wall time (353.89s CloudyCPU),236zones and3iterations, without warnings
or convergence failures. Its H+ weighted temperature is13177.67K versus
13462.39K for ordinary composition. Both actual printed/every-zone C/N/O
abundances, all29line identities, intrinsic/emergent sums and final stops pass.

Actual enhanced/ordinary intrinsic responses are N IV7.825, C IV0.7835,
He II+O III0.8880, N III8.7837 and C III0.8850. Pure nitrogen-flux rescaling
would predict[10,1,1,10,1] and is rejected as a measurement-model shortcut.
This is a numerical physical response, not evidence for enhanced nitrogen in
the source. `mom_cloudy_focused_pair.json` preserves both complete thermal
models and separate full-covariant native likelihoods. The full20environmental
grid is not represented as executed.

Among these two fixed environmental models, ordinary composition has the
smaller profiled chi2 for all six original-wavelength noise/resolution choices.
The DUMMY wavelength/generic-point alternative weakly prefers enhanced
nitrogen by only0.224chi2 under empirical row-plus-column noise (0.352formal).
These differences are conditional comparisons; no grid counts, discovery
significance, abundance odds or prior-independent interval follows. Ordinary
composition remains adequate under the existing empirical transport. The
new RATE-based variance audit is a separate pending measurement dependency;
old noise alternatives do not become empirical truth by fitting this pilot.

The held-out pilot took0.251s. Ordinary/enhanced predictive quadratics for
RATE groups03,05,07 are respectively188.08/188.91,208.03/210.55 and
158.60/156.43 for208continuum-projected dimensions per group. Normalization
was learned only from the two other groups, and its nonnegative truncated
uncertainty propagated. None of the six training amplitudes reaches the
nonnegative fit boundary. These similar scores do not identify composition
and cannot bound a shared calibration error. They are conditional
moment-matched diagnostics, not calibrated p-values or population evidence.

## Declared complete20pilot retry after validated pair

After independent validation of the original nonlinear thermal pair and the
OpenBLAS emitted-line/average-temperature equivalence, use one consistent
OpenBLAS executable for the complete original20model pilot. Reuse only its
validated ordinary control and rerun the enhanced partner once on OpenBLAS,
comparing that actual output to the original LP64 partner before extending.
Then execute the18remaining originally declared controls, with at most2workers
and a hard1200s wall cap per model. This authorizes19new runs of existing
parameter choices, no added physics, no new acquisitions and no grid growth.
The expected remaining runtime is55–90minutes; the hard computation ceiling
is19×1200process-wall seconds. Stop and cancel unstarted futures on the first
failed convergence, identity, completeness or timing check, retaining already
running outcomes separately. Never replace a capped line by zero.

The question is whether density, ionization, hardness and metallicity controls
change observational discrimination or supply ordinary alternatives, under a
complete thermal solution. The dominant measurement uncertainty is being
revised independently using RATE-stage variance provenance. Physical model
execution can proceed while that audit runs, but the historical empirical
noise alternatives must stay conditional controls. Connect this completed
pilot to the independently validated new covariance before integrated
interpretation; do not treat the old covariance as measured truth.

The consistent-backend enhanced control completed in443.312s,236zones and
3iterations, with exact saved58line-response/five-average-temperature equality
to the original partner and exact input bytes. Adaptive profiles remain
separately bounded in `mom_cloudy_enhanced_backend_control.json`. This second
runtime differs from the earlier378.811s partner; a single benchmark cannot
isolate host load or establish a universal backend speedup. The complete
original20pilot now uses one executable; the original pair remains a versioned
control and duplicate reductions are never pooled. The remaining18models
started only after this declared cross-backend preflight passed.

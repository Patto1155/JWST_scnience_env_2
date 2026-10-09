# Conditional enrichment and formation constraints

9 October 2026. This experiment starts from the verified takeover baseline.
It evaluates published abundance inferences conditionally; it does not measure a
new abundance, fit a stellar population, or identify a preferred polluter.

## Inputs, reproducibility, and uncertainty

`data_sources/pilot/enrichment_benchmarks.json` transcribes specific primary-paper
table entries and gives their URLs, versions, locations, and assumptions. The
SMS elemental yields were checked against both [Nagele & Umeda v4, Table
1](https://arxiv.org/html/2304.05013v4) and [Ebihara et al. v3, Table
1](https://arxiv.org/html/2601.04344v3). These four discrete stellar models start
at 0.1 solar metallicity; using their yields in a different ambient composition
is a sensitivity scenario, not a self-consistent new stellar calculation.

```bash
python -m discovery.enrichment_constraints --output research_output/enrichment_constraints.json
python -m pytest tests/test_enrichment_constraints.py -q
python -m ruff check discovery/enrichment_constraints.py tests/test_enrichment_constraints.py
```

The saved output pins the benchmark input SHA256. There are **432 deterministic
mixing cases**, not 432 simulations or posterior draws. Published marginal
interval endpoints are sensitivity cases; no covariance or independent Gaussian
likelihood is invented. Tests cover mass-to-number conversion, elemental-budget
closure, retention scaling, pristine-dilution invariance, formation-time inversion,
and impossible targets.

[Naidu et al. v2](https://arxiv.org/html/2505.11263v2) reports Cue
`[N/C]=0.90 (+0.29,-0.63)`; its adopted solar log N/C is -0.60. The elemental
number ratios corresponding to the three endpoints are 0.468, 1.995, and 3.890.
Cue omits N IV], and several model posteriors approach grid boundaries. A separate
ionic-abundance analysis in the same paper is stronger; it must not be silently
substituted for Cue. UNITE already models wavelength-dependent instrumental LSF:
an unconstrained intrinsic width does not mean resolution was ignored.

## Clock experiment: a hiatus is not the complete history

Using Astropy's Planck18 cosmology, the Universe is **283.071 Myr** old at
z=14.44. Applying only the quoted redshift endpoints gives 282.520–283.624 Myr;
this is not a cosmological age posterior. Available time since specified onset:

| Assumed onset redshift | Time available at z=14.44 (Myr) |
|---|---:|
| 20 | 104.959 |
| 25 | 154.010 |
| 30 | 184.113 |
| 40 | 218.236 |

[Kobayashi & Ferrara v2](https://arxiv.org/html/2308.15583v2) supplies a
GN-z11 fiducial dual-burst history of **204 Myr**, including a 100 Myr first
episode, 100 Myr pause, and a young second burst. It cannot be transplanted into
a z=20 onset: it exceeds that budget by **99.041 Myr**. The same clock permits
this duration if onset is z≥**34.960**; that is a necessary timing condition,
not evidence for such early formation. Their shorter **103 Myr** example has
only **1.959 Myr** to spare after z=20. Neither is a MoM-z14 abundance fit.

The timing check rejects the *fiducial history plus z=20-onset combination*, not
WR enrichment in general. A 40–150 Myr AGB delay also has mixed feasibility:
40 Myr requires onset z≥16.084, whereas 150 Myr requires z≥24.478. A luminous
recent burst is not a hard upper limit on the age of all stars or on a prior
enrichment episode. The complete formation prior matters.

## Yield experiment: bound the polluted gas parcel

For ejected carbon and nitrogen masses C and N, the pure-ejecta number ratio is
`(N/14)/(C/12)`. Uniform mixing with ambient material of lower N/C cannot exceed
that ratio. Equal retention is a conditional assumption, not a measured property.

| Initial mass (solar masses) | Channel | Pure-ejecta [N/C] on MoM solar scale | Can reach the Cue median with lower-N/C ambient gas? |
|---|---|---:|---|
| 1,000 | wind | 0.767 | No |
| 10,000 | wind | 2.155 | Yes |
| 50,000 | wind | 2.206 | Yes |
| 100,000 | wind/explosion | 1.693 | Yes |

The 1,000-solar-mass *specific tabulated yield* does not reach 0.90 dex under
these conditions, but can reach the lower 0.27-dex endpoint. Differential
nitrogen/carbon retention or an already enriched ambient phase changes the
bound. This is not a statistical rejection of that stellar population.

The maximum ambient gas mass per event obeys the conserved-element relation

\[
 M_{\rm gas,max}=\frac{f_{\rm retain}(Y_N/14-R_tY_C/12)}
 {n_{C,\rm amb}(R_t-R_{\rm amb})}.
\]

Here ambient nuclei per solar mass are expressed in common solar-mass/atomic-mass
units. The numerator must be positive. In this calculation hydrogen mass
fraction is 0.75, ambient `[O/H]=-1.38`, initial `[N/C]=0`, target `[N/C]=0.90`,
and all elements have full retention. The two ambient C/O cases illustrate why
a nitrogen mass alone does not determine the enrichment of an entire galaxy:

| Stellar yield | Maximum gas mass, ambient [C/O]=0 | Maximum gas mass, ambient [C/O]=-0.65 |
|---|---:|---:|
| 10,000 solar masses | 332,719 solar masses | 1,486,203 solar masses |
| 50,000 solar masses | 29,557 solar masses | 132,028 solar masses |
| 100,000 solar masses | 317,418 solar masses | 1,417,853 solar masses |

At 10% equal retention, all these mass bounds fall by exactly ten. Changing
ambient C/O by -0.65 dex raises them by 4.47. Ambient oxygen endpoint changes
produce a further factor of 16.2 between the lowest and highest assumed
metallicity. Those systematic scenarios are larger than a rounding error and
are unmeasured here. No emitting gas mass is known from this experiment.

The output also computes the resulting C/O, N/O, and O/H, including ejecta
hydrogen. For example, a 50,000-solar-mass yield mixed into the carbon-poor case
at its mass bound gives log N/O=-0.596, log C/O=-0.896, and 12+log O/H=7.314.
Matching N/C alone therefore neither demands a giant global nitrogen inventory
nor establishes that this polluter formed. The explosion's equal-retention case
needs a dynamical check before being physically preferred.

## Rotation, VMS, and a dilution test

[Nandal, Sibony & Tsiatsiou, Table 2](https://arxiv.org/html/2405.11235v1)
provides four selected top-heavy Pop III/extremely metal-poor benchmarks. Their
N/C on the *MoM* solar scale is 0.45, 0.73, 0.31, and 0.37 dex. All overlap the
broad published interval; all are below its 0.90 median. They have distinct
predicted C/O and carbon-isotope ratios. They are selected rounded cases, not
the full allowed parameter space or a transferred MoM fit.

The exact mathematical discriminator is that **adding primordial gas changes
O/H but preserves N/C, N/O, and C/O**. It cannot move a chosen rotating model
to an arbitrary nitrogen/carbon ratio. Metal-bearing mixtures, different mass
cuts, rotations, and ages can. Future resolved C/O and density diagnostics can
test the selected yields jointly; current independent marginal intervals cannot
rank these mechanisms.

[Vink v3, Section 5](https://arxiv.org/html/2310.10725v3) estimates approximately
one solar mass of nitrogen per 300-solar-mass LMC-like VMS over approximately two
Myr. This is a useful prompt-timescale benchmark, but its stellar metallicity
and absent accompanying C/O grid prevent a quantitative MoM likelihood here.
No yield or posterior weight is fabricated for the missing grid.

An additional algebraic thought experiment converts initial carbon nuclei to
nitrogen while conserving C+N nuclei: the three N/C endpoints require processing
14.8%, 58.2%, or 74.4% of initially solar-ratio carbon nuclei. This is not a
stellar yield calculation. It illustrates carbon-denominator sensitivity, not
the age or stellar mass of a galaxy.

## Formation explanations and the limits of this dataset

Conditioning on the paper's stellar-mass model, the median mass is
10^8.1 solar masses. With Planck18 cosmic baryon fraction, simple accounting
requires a halo of at least **7.96×10^8 solar masses** at complete conversion of
its initial cosmic baryon allowance to surviving stars; 10% and 1% conversion
instead require 7.96×10^9 and 7.96×10^10 solar masses. Gas still present and
baryons lost increase the requirement. IMF-dependent stellar-mass changes and
centrally concentrated baryons invalidate using this as a measured halo mass.

Thus burst timing, stellar mass-to-light ratios, and conversion efficiency give
testable alternatives for bright early galaxies. This single selected source
does not supply a halo mass function, survey completeness, duty cycle, or cosmic
variance measurement. Dark-matter changes cannot be ranked from these data, and
black-hole-powered continuum or ionization cannot be inferred from nitrogen
alone. A quantitative BH test needs separated high-ionization lines and broad
components, jointly checked against resolved morphology and extraction effects.

## Highest-value follow-up

1. Link the independently refitted spectrum's masks, LSF, covariance, and
   extraction sensitivity to the chemical-inference guard. New line measurements
   remain observations; they do not inherit the published Cue posterior.
2. Acquire a versioned emissivity/photoionization grid spanning ionization,
   electron temperature and density, including N IV], N III], C IV, C III], and
   separated He II/O III]. Fit with flux covariance; compare model-dependent
   abundances before ranking yields.
3. Constrain emitting gas mass and gas-phase C/O independently. These determine
   whether enrichment is local or demands many retained polluters. Resolve the
   stellar/nebular He II contribution before treating He II as a VMS signature.
4. Run a baryon-budget and UV-luminosity-function comparison on a completeness-
   controlled population; a single object and a conditional mass cannot establish
   a cosmological anomaly.

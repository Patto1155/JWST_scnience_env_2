# Conditional formation predictions and the population test still required

9 October 2026. This round builds on merged native spectroscopy, atomic/Cue and
enrichment analyses. It computes explicit assembly predictions from a frozen,
model-dependent stellar-mass input. It does not refit the SED, measure a halo,
identify a polluter or infer a cosmological anomaly.

```bash
python -m discovery.formation_predictions \
  --output research_output/formation_predictions.json
python -m pytest tests/test_formation_predictions.py tests/test_atomic_enrichment.py -q
```

The generator requires only tracked inputs. The output pins the primary
benchmark, explicit scenario and frozen native-enrichment bytes. Its **720
history cases, 216 baryon budgets and 80 inverse histories** are deterministic
sensitivity choices, not simulations, posterior draws or model probabilities.
The independent native ionic numerical-replay regression now uses the tracked
PR44 artifact; exact lineage/schema/counts and tight `1e-12` numerical tolerance
are preserved. Tests use independent numerical integration for mass and
half-mass histories, conservation controls and selection/scatter counterexamples.

## Mass convention and published modeling limits

[Naidu et al. v2, Table 1 and §3.2.2](https://arxiv.org/html/2505.11263v2)
reports log stellar mass **8.1 (+0.3,-0.2)** from Prospector. The text labels
total stellar mass without specifying a formed/surviving conversion. The
[official Prospector FAQ](https://prospect.readthedocs.io/en/stable/faq.html)
states that its default mass is cumulative formed mass; surviving mass requires
the returned mass fraction. The author's configuration/postprocessing is still
needed to resolve the convention. We evaluate both interpretations rather than
declaring either confirmed.

Table 1 also gives model-dependent SFR over 5 Myr **13.0 (+3.7,-3.5)**,
over 50 Myr **2.2 (+1.5,-0.6)** solar masses/year, and `t50` **4.0
(+10.0,-1.4) Myr**. They are transcribed into the versioned scenario input.
Comparisons assume nested trailing time means and a half-mass lookback time;
exact author definitions/configuration remain required. Individual marginal
endpoint membership is not a joint likelihood. The quoted mass is held fixed
only for bookkeeping: changed IMF, histories and mass-to-light ratios require
a new stellar-population fit.

## History predictions: rapid brightening need not date all stars

For a rising exponential envelope, active SFR today is `S`, the uniformly
interleaved active fraction is `d`, and effective integrated return is `R`:

\[
M_{\rm surv}=(1-R)dS\tau(1-e^{-T/\tau}).
\]

The constant-history limit replaces the final factor by `T`. Years are used in
the rate conversion. Duty is an assumed time average, not a measured UV
visibility probability. A physical fit needs time-dependent stellar return,
actual burst timing and emission kernels, especially for short histories.

Planck18 gives **104.959 Myr** between assumed onset z=20 and z=14.44. At quoted
median mass, interpreting it as surviving mass and assuming `R=0.4`:

| Assumed assembly history | Required active SFR (solar masses/year), d=1 | d=0.1 |
|---|---:|---:|
| Constant since z=20 | 2.00 | 19.99 |
| Rising, 10-Myr e-fold time, since z=20 | 20.98 | 209.83 |
| All mass assembled in the last 4 Myr, constant | 52.46 | 524.55 |

If the quote instead denotes **formed mass**, those rates multiply by 0.6 at
this assumed return fraction. The last row tests complete recent assembly; the
published `t50` is not an assertion that the galaxy began 4 Myr ago.

A useful conventional counterexample is a continuous rising history since
z=20 with the median quote interpreted as formed mass:

| Rising e-fold time | Predicted 5-Myr mean SFR | Predicted 50-Myr mean SFR | Half-mass lookback (Myr) |
|---|---:|---:|---:|
| 5 Myr | 15.92 | 2.518 | 3.466 |
| 10 Myr | 9.907 | 2.501 | 6.931 |

Both rows lie within all three published marginal endpoint intervals under
the stated definitions. This demonstrates conditional feasibility, not a fit
or preference. The predictions change with the mass convention, return,
earlier populations and SED model. In contrast, a constant history across the
whole z=20 budget predicts an old half-mass time and a weak recent rate; it
cannot reproduce those same endpoint constraints at the median assumptions.

The inverse calculation exposes falsifiable combined hypotheses. If the
surviving-mass convention, `R=0.4`, d=1 and a hypothetical active SFR of
10 solar masses/year were fixed, a constant history needs **20.98 Myr**;
a 30-Myr rising envelope needs **36.06 Myr**. A 10-Myr rising envelope can
never build that mass at that present rate, even with arbitrarily early onset:
its integrated mass has an asymptotic ceiling. This rejects that combination,
not early galaxy formation. The earlier 204-Myr history plus z=20-onset
timing failure remains separate in [the enrichment report](ENRICHMENT_CONSTRAINTS.md).

## Baryons, outflow and local enrichment

For a closed gas parcel with recycled return, permanently lost wind mass
`eta × M_formed`, remaining gas and no external inflow/ex-situ stars:

\[
M_{\rm gas,initial}\ge M_{\rm surv}+M_{\rm gas,remaining}+\eta M_{\rm formed}.
\]

This prevents counting returned gas twice. Dividing by the Planck18 cosmic
baryon fraction and the assumed initially available baryon fraction gives a
necessary halo allowance, not a measured halo or a cooling calculation.
For the surviving-mass median, `R=0.4`, no remaining gas and full initial
allowance, minimum halo budgets are **7.96×10⁸**, **2.12×10⁹** and
**7.43×10⁹ solar masses** for eta=0,1,5. Thirty-percent initial availability
raises every bound by 3.33. Inflow, reaccreted winds and mergers change this
closed-parcel interpretation.

Using the frozen PR39 native empirical point, assumed stage ratio k=0.3 and
carbon-poor ambient composition, enriching a *hypothetical* one-million-solar-mass
ambient parcel with the selected 50,000-solar-mass SMS yield needs **7.316 event
equivalents** at full retention or 73.16 at tenth retention. These cost
**0.174%/1.74%** of cumulative formed mass under the surviving-mass convention
and assumed `R=0.4`; the formed-mass convention gives 0.291%/2.91%.
Whole-event rounding requires adjusted dilution/retention to match an exact
target. Neither gas mass nor IMF allocation is observed here.

Crucially, at assumed k=0.3 the initial solar-N/C ambient ionic ratio is
**0.837**, inside the native reference Fieller set **[0.146,21.708]**.
The data therefore establish **no positive minimum polluter fraction** under
this reference treatment. Point budgets must not become discovery claims.

## A testable cosmology contract requires selected populations

The implemented discrete operator is

\[
\lambda_{\rm selected}={\cal R}\,[\lambda_{\rm parent}\odot p_{\rm visible}]
 +\lambda_{\rm contamination}.
\]

Each response column is a subprobability distribution across selected bins,
retaining missed sources and bin scatter. Its supplied control uses two
arbitrary unit parent classes and gives selected weights 0.08/0.22; these are
synthetic operator checks, not observed population counts. UV afterglow and
burst timing prevent substituting time duty directly for visibility.

Competing cosmologies must supply versioned halo abundances, volumes and field
variance; astrophysical assembly/IMF/dust/emission and visibility models; and
calibrated magnitude/size/SED/position selection, scatter and contamination.
They must predict the **same selected observables** before joint field
likelihoods or predictive checks can discriminate them. Present screen counts
and areas do not meet that contract.

Priorities are author SED configuration/posterior mass conversion and time-bin
definitions; joint stellar/nebular fits with physical return kernels; emitting
gas, wind/retention and halo constraints; then calibrated completeness and
contamination across independent fields. No cosmological or mechanism
probabilities are reported.

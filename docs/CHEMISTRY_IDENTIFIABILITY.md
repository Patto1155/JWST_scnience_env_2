# What the actual spectrum can identify about enrichment

This round builds on merged enrichment PR #17 and measured-spectrum PR #18. It
uses fitted line **covariances and extraction scenarios**, rather than treating
the published Cue abundance posterior as the result of our own spectrum fit.
There is still no calibrated atomic/photoionization grid, so no new elemental
abundance or model probability is reported.

```bash
python -m discovery.chemistry_identifiability --output research_output/chemistry_identifiability.json
python -m pytest tests/test_chemistry_identifiability.py tests/test_enrichment_constraints.py -q
```

The output pins both input-report hashes, summarizes all 31 spectral scenarios,
and evaluates 13 numerical abundance targets. Tests retain covariance, signed
Fieller sets, disconnected/unbounded uncertainty sets, and incompatible mixing
cases. Alternate extractions share exposures; they are sensitivity checks rather
than independent likelihoods.

## The missing physical map is quantitatively important

Write the observed integrated line ratio schematically as

\[
 \frac{F_{\mathrm{NIV}}+F_{\mathrm{NIII}}}
 {F_{\mathrm{CIV}}+F_{\mathrm{CIII}}}
 = Q_{\rm eff}\,\frac{N}{C}.
\]

The factor Q represents effective emissivity and ion-fraction differences. It
also depends on temperature, density, radiation, geometry, chemical cooling,
and line transfer. It need not be constant when abundances change. Defining Q
does not calibrate it: this experiment asks what factor each conditional target
would *require*, not which factors real nebulae permit.

The stored-1D baseline gives line ratio **1.039**, with a formal conditional
Gaussian 95% Fieller set **[0.448, 2.159]**. Across extraction, nominal LSF,
continuum, multiplet, and assumed covariance choices, point ratios span
**0.642–1.336**. No spectrum-derived N/C is attached to those measurements.

For example, the same central line ratio would imply the following **only if**
the stated unmeasured Q were fixed:

| Assumed Q | Conditional [N/C] point on MoM's solar scale |
|---|---:|
| 2.0 | 0.316 |
| 1.0 | 0.617 |
| 0.5 | 0.918 |
| 0.2 | 1.316 |

The published Cue median requires **Q=0.521**, with conditional measurement-only
95% set **[0.225, 1.082]** and spectral-scenario point range **0.322–0.670**.
The measurement alone identifies a product of abundance and this factor.
Assigning Q=1 because the ions have similar names is unjustified.

The [separate ionic calculation in Naidu et al. v2,
Section 3.2.3](https://arxiv.org/html/2505.11263v2) reports [N/C] values ranging
from approximately 1.3 to 1.7 across electron-temperature models spanning
0.5–3×10^4 K. These are distinct from Cue's 0.90 median; this temperature range
is not a new confidence interval. Those two targets require central Q=**0.207**
or **0.0826** in the schematic map. An actual emissivity grid must test whether
these factors are physically attainable with all lines and their covariance.

## Which numerical mechanisms could be distinguished?

| Pinned abundance target | Type of target | Required Q for central observed ratio |
|---|---|---:|
| 1,000-solar-mass SMS | Pure-ejecta N/C ceiling under equal retention | 0.707 |
| 10,000-solar-mass SMS | Pure-ejecta N/C ceiling under equal retention | 0.0290 |
| 50,000-solar-mass SMS | Pure-ejecta N/C ceiling under equal retention | 0.0257 |
| 100,000-solar-mass SMS | Pure-ejecta N/C ceiling under equal retention | 0.0839 |
| Top-heavy rotating EMP, above remnant | Selected mixed-ISM prediction, [N/C]=0.73 | 0.771 |
| Top-heavy rotating Pop III, above remnant | Selected mixed-ISM prediction, [N/C]=0.45 | 1.468 |

Yield ceilings are not predictions of an unmixed observed gas phase. For the
1,000-solar-mass yield, Q below 0.707 would require a central elemental N/C
above its ceiling, under the equal-retention/lower-N/C ambient assumptions.
Q above that value would allow dilution to the central required ratio. Since
Q is not measured and its conditional required-factor set is broad, the actual
line spectrum does not exclude this yield. Conversely, high SMS yield ceilings
cannot make their formation or retention automatic.

The numerical WR benchmark presently supplies a **history and clock**, not a
complete N/C yield grid. The VMS benchmark supplies approximately one solar mass
of nitrogen per star, but lacks accompanying carbon/oxygen ejecta. Neither gets
a fabricated Q prediction or posterior weight. Ignoring all coejected carbon
gives an optimistic VMS gas budget of **4,648–20,761 solar masses per star** for
the Cue median, with full nitrogen retention and the two previously specified
ambient C/O cases. This uses an LMC-like stellar estimate; it is not a MoM yield
calculation. Carbon ejection or incomplete retention lowers that ceiling.

## Joint elemental consistency prunes an N/C-only comparison

At each SMS mixing bound, we also compare resulting 12+log O/H and log C/O
against the published marginal endpoint box **[6.77, 7.98] × [-1.13, -0.52]**.
This is a necessary endpoint compatibility check, **not a joint credible region**
and not a likelihood. Each number below counts specified deterministic grid
choices, including three retention scalings; it is not a probability.

| Fixed N/C target | 1,000 SMS | 10,000 SMS | 50,000 SMS | 100,000 SMS |
|---|---:|---:|---:|---:|
| Cue median [N/C]=0.90 | 0/36 | 24/36 | 12/36 | 12/36 |
| Separate ionic [N/C]=1.30 | 0/36 | 6/36 | 12/36 | 12/36 |
| Separate ionic [N/C]=1.70 | 0/36 | 0/36 | 12/36 | 0/36 |

At 1.70 dex, the 10,000-solar-mass yield still reaches N/C but none of this
chosen background grid also satisfies both other marginal boxes. The
100,000-solar-mass yield's ceiling is 1.693 dex, only **0.007 dex** below this
target; stellar-model systematics overwhelm interpreting that algebraic gap as
evidence against a population. Different ambient compositions, preferential
retention, or other stellar yields can change every grid result. No mechanism
is rejected globally.

Among the median-target compatible cases, the 50,000-solar-mass model enriches
ambient gas parcels of approximately **2.67×10^3–1.32×10^5 solar masses**; its
1.70-dex cases instead allow **2.98×10^2–1.35×10^4 solar masses**. This focuses
the next question on the emitting gas mass and localized pollution, rather than
equating an emission-weighted ratio with the chemistry of the whole galaxy.

The same pinned hydrogen and helium ejecta give an additional **conditional
gas-abundance prediction**. With ambient X_H=0.75 and X_He=0.25, neglecting trace
metals, the initial He/H number ratio is 0.08333. At the median N/C mixing bound,
the carbon-poor-background examples predict He/H=**0.08382, 0.08577, and 0.09329**
for the 10,000, 50,000, and 100,000-solar-mass yields. The 50,000-solar-mass
1.70-dex case instead predicts **0.10001**. These numbers assume full equal
retention and homogeneous mixing; they are not inferred from the UV blend.
Separated helium and hydrogen recombination diagnostics, with ionization
corrections, could test these dilution-linked predictions.

## Useful observations rather than invented certainty

The measured NIV/CIV ratio is **1.442**, versus NIII/CIII **0.497**. Their formal
95% sets are [0.584, 4.710] and **[-0.271, 1.827]**. The negative second endpoint
is retained from the signed-amplitude model; it demonstrates limited information,
not negative physical abundance. A nebular calculation must explain both ion
stages together, rather than choose a convenient sum-to-abundance conversion.

The unresolved He II+O III] blend/C III] ratio is **1.177**, with conditional
95% set [0.137, 3.676]. It cannot separately measure helium abundance, oxygen,
stellar-wind He II, or a black-hole ionizing continuum. The highest-value next
observations are resolved O III]/He II, density-sensitive multiplet ratios,
additional ion stages, and an independent ionized-gas mass. Combined with a
versioned atomic/photoionization grid, these can break the present nuisance
degeneracy and test WR/VMS/SMS/rotation predictions quantitatively.

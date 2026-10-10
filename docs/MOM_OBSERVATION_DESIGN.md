# Conditional UV observation design

A source-specific LSF, line sensitivity and density have not been measured here.
This experiment calculates which *new measurements* could resolve a specific
ambiguity, before requesting any observing time. At assumed z=14.44, nominal
medium-resolution grating response can already separate narrow N IV and C III
components in an idealized white-noise experiment. High resolution alone does
not overcome a broad intrinsic source or an unknown response.

The [predeclared plan](../data_sources/pilot/observation_design/plan.json) fixes
Te=20,000K, ne=1,000 versus100,000cm−3, intrinsic Gaussian FWHM=0/300/1,000km/s,
and a conditional expected squared separation target9. It assumes known
centroid, width, continuum, white stationary Gaussian noise and shared source
geometry. These are optimistic design assumptions, not empirical calibration
or a density posterior. The nominal mode specification was refined to actual
primary wavelength-dependent grating curves rather than constant central R.

## Inputs and new measurement targets

The immutable PyNeb1.1.32 version2 components preserve both N IV members and
atomic provenance: SHA256
`692ce2fe0ca5463708abfa3c232378f3aebe22ff9b96f97d779091d54ac5f474`.
No new line-emissivity or yield assumptions are substituted into earlier fits.
Four small primary dispersion FITS from
[STScI JDox](https://jwst-docs.stsci.edu/jwst-near-infrared-spectrograph/nirspec-instrumentation/nirspec-dispersers-and-filters)
are committed with exact URL/byte/hash receipts. Their response is for a fully
illuminated2.2pixel resolution element, **not a MoM source LSF**. Filter ranges
are separately enforced; the tabulated grating response extends beyond them.
For MOS, aperture-specific detector edges and gaps must be checked in an
[APT target-info/ETC design](https://jwst-docs.stsci.edu/jwst-near-infrared-spectrograph/nirspec-operations/nirspec-mos-operations/nirspec-mos-wavelength-ranges-and-gaps).

| Line components | Observed wavelength at assumedz14.44 (µm) | Narrow closest-pair separation (km/s) | Nominal first design |
|---|---|---:|---|
| N IV1483/1486 |2.290248 /2.295150|641.0|G235M/F170LP; compare G235H source-LSF alternatives|
| C IV1548/1551 |2.390427 /2.394406|498.6|G235M/H; transfer/stellar absorption remain separate|
| He II1640 /O III1661 /1666 |2.532808 /2.564289 /2.572536|closest O/O≈962.6|G235M/H with free He/O amplitudes|
| N III multiplet |2.697095–2.708168|closest≈176.2|G235H; intrinsic width can blend members|
| C III1907/1909 |2.943919 /2.947085|322.3|G235M/H; G395M/H alternative with gap check|

N V1239/1243 falls at1.912738/1.918883µm. The Cloudy C II2326.93 **air**
line-list label gives an approximate target3.592780µm; a vacuum conversion is
required for exact instrumental wavelength assignment.
additional stages have nominal near-IR wavelength access, but predicted flux,
transfer and sensitivity are needed before feasibility. Hβ, [O III]5007 and
[N II]6583 lie at≈7.506/7.731/10.165µm using Cloudy's air wavelengths as
approximate targets. They require a different instrument/response model.
N V near the break is not assumed a guaranteed nebular abundance diagnostic.
No missing line is assigned zero flux.

## Measurable design consequences

For unit-area Gaussian components, the code integrates the exact continuous
white-noise inner product. Dividing by component norms gives a correlation
matrix; its inverse diagonal gives component flux-error inflation relative to
isolated lines. The shape contrast profiles the competing model's free total
amplitude. For a truth-template matched SNR S, the expected separation is
S² times the fractional residual shape information. Target9 is an illustrative
conditional distance, **not a calibrated rejection rate**.

| Group /nominal curve | Intrinsic FWHM (km/s) | Component conditioning | SNR for ne1k→1e5 shape contrast |
|---|---:|---:|---:|
| N IV/G235M |0|1.005|9.39|
| N IV/G235H |0|1.000|9.37|
| N IV/G235H |300|1.008|9.40|
| N IV/G235H |1,000|3.650|17.55|
| C III/G235M |0|1.172|6.15|
| C III/G235H |0|1.000|5.75|
| C III/G235H |300|1.591|7.04|
| C III/G235H |1,000|14.015|19.93|

The low/high density examples change the fixed Te ionic component weights;
they do not identify density from current data or assume that N IV and C III
arise from the same gas. The comparison does not test nearby densities on a
saturated low-density plateau. Instrumental gains cannot be ranked by these
SNR numbers alone, since throughput/background differ by mode. Extra centroid,
width, continuum and multiple-component nuisance freedom can reduce shape
information. Density constraints need all of those in the final likelihood.

He/O separation is far less demanding geometrically than a narrow C III
component ratio: G235M/H give almost diagonal component inner products at
0/300km/s; even1,000km/s gives maximum component-error inflation≈1.049/1.042.
That supports a free-He/O observing target rather than interpreting the current
fixed blend as an oxygen abundance. The actual faint component's sensitivity is
not fixed by geometrical separation.

## Exposure assumptions and scientific stopping point

[STScI sensitivity documentation](https://jwst-docs.stsci.edu/jwst-near-infrared-spectrograph/nirspec-performance/nirspec-sensitivity)
uses current ETC benchmark scenes; its continuum benchmarks do not provide this
source's integrated-line sensitivity. **No absolute exposure time is supplied.**
`exposure_scale` accepts a source/mode/template-specific *random-noise* SNR at t0.
With no systematic floor, t/t0=(required/reference)². Illustrative SNR20 versus5
requires16t0; an independent fixed SNR30 systematic ceiling changes that to28.8t0;
a ceiling10 makes SNR20 unattainable. These inputs are examples, not ETC outputs.
The function does not scale the current prism SNR into grating observing time.

Before a proposal, specify source morphology/slit position, line fluxes,
centroid/width alternatives, background, aperture, readout, nod/dither strategy,
coverage gaps, calibrator/response uncertainty and actual ETC version/output.
Three existing RATE groups do not empirically constrain all shared systematics;
more photons alone do not remove that uncertainty.

The experiment rejects the blanket premise that high R is always required to
geometrically separate the listed narrow pairs. It does not reject the utility
of high R for calibration, kinematics, broader source hypotheses or weaker
components. No elemental N/C, stellar polluter or cosmological conclusion changes.
Thermal-balance model-pair contrasts are a separately versioned follow-up after
the complete Cloudy pilot is merged.

## Reproduction and validation

```bash
python -m data_pipeline.observation_design_inputs
python -m tools.jwst.observation_design
python -m pytest tests/test_observation_design.py
```

[Output](../research_output/mom_observation_design.json) contains36 response cases,
line targets, density weights, conditioning, SNR thresholds, input hashes and
null absolute times. Eleven tests check independent numerical quadrature,
independent amplitude minimization, response pins/range guards, broadening,
fixed floors and exact numerical replay. A separate reviewer is required
before merge. Code/analysis executes in under2seconds on the locked environment.

Unique newly selected inputs total1,668,841bytes:83,520 dispersion products and
1,585,321 documentation bytes. A prior exploratory fetch of the same disperser
page adds551,357transfer bytes, separately from unique input selection. There
were no failed transfers or paid resources. Raw dynamic HTML is read/provenanced
but not committed; exact scientific FITS are committed and bounded-regenerable.

## Wavelength-convention correction

The original C II target was incorrectly labeled vacuum. Independent review
identified the Cloudy default air convention above2,000Å. Direct source inspection
verifies `source/prt.h`, `init_defaults_preparse.cpp`, `lines_service.cpp` and
`data/blends.ini` in the pinned C23.01 archive; exact member hashes are in
[the convention receipt](../data_sources/pilot/observation_design/cloudy_line_convention.json).
The corrected target is explicitly an approximate air-based wavelength, like the
optical targets. Its numeric approximation is preserved. All36 density/UV
response cases use vacuum wavelengths below2,000Å and remain exactly unchanged.
No conversion or empirical calibration is claimed by this correction.

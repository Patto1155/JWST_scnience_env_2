# Versioned atomic map: what the measured nitrogen lines imply conditionally

This experiment resolves the missing **ionic emissivity** dependency. It does
not resolve photoionization, line transfer, or the elemental ionization correction.
The observed flux fit and its complete five-group covariance remain the inputs;
the published Cue abundance posterior is not treated as measured by this code.

## Reproduce

```bash
python -m data_pipeline.atomic_inputs /path/to/atomic-inputs
PYTHONPATH=/path/to/atomic-inputs/pyneb-runtime python -m tools.jwst.atomic_grid \
  --generate-grid research_output/mom_atomic_grid.json
python -m tools.jwst.atomic_grid
python -m pytest tests/test_atomic_grid.py -q
```

Only regeneration requires the optional PyNeb package. The committed 28-cell
grid and covariance analysis replay using the existing research environment.
PyNeb **1.1.32**, released 27 July 2026, is pinned to its publisher SHA256
`96a63479536b4e53fdb36e1da20d72b9291cf920e042d765dd4a0c4ca3160cbe`;
the wheel is **28,751,057 bytes**. Cached and new downloads both verify against
those independent pins. Acquisition extracts into a separate directory and does
not alter the shared environment. Every actually used atomic file has its own
hash, size and bibliographic source in the grid. The 100 MiB atomic allocation
also accommodates the separately acquired Cue v0.1 archive (31,885,220 bytes).

## Atomic coverage and explicit assumptions

The grid covers electron temperatures **5,000–30,000 K** and electron densities
**100–100,000 cm^-3**. It sums the same N III] quintuplet and C III]/C IV doublets
as the measured flux templates. N IV] retains **1486.496 only**, matching the
stored fit; it does not silently add the adjacent 1483 line. UV O III] requires
the 6-level `o_iii_coll_TZ17.dat`: PyNeb's default five-level collision set cannot
evaluate 1661/1666. He II uses the Storey–Hummer 1995 case-B FITS table. O III]
and He II emissivities are included but the observed blend does not separate
their amplitudes: five groups for six ionic amplitudes have rank five.

The calculation assumes homogeneous common Te/ne, optically thin collisionally
excited C IV, no stellar-wind contribution or resonant transfer, no differential
attenuation, and common emission-measure weighting. These are modeling choices,
not properties established by this PRISM spectrum. Atomic-data alternatives and
multiphase geometry are not averaged into an invented uncertainty distribution.
The stored spectrum used equal NIII/CIII multiplet weights; actual PyNeb weights
depend on density. This post-hoc transformation of group totals is conditional
on those spectral templates, **not a density-self-consistent spectrum fit**.
Native re-extraction and atomic-multiplet spectral template refits are required
before strengthening that inference.

## Executed results

For each group, emissivity epsilon is `j / (ne * n_ion)` in erg cm³ s^-1.
The code applies the linear `F/epsilon` operator to the full covariance before
forming Fieller uncertainty sets. It does not clip signed or unbounded sets.

With nominal slit resolution, Te=20,000 K and ne=1,000 cm^-3, the measured
two-stage ionic ratio `(N2+ + N3+) / (C2+ + C3+)` is **8.828**, with formal
conditional Gaussian 95% Fieller set **[3.878,18.306]**. Relative to the paper's
solar log(N/C)=-0.60, this corresponds to an **ionic**, solar-relative logarithm
of **1.546 dex**, with transformed interval **[1.189,1.863] dex**. The same fixed
cell under the generic point LSF gives **8.876 [4.276,17.818]**. Alternative LSF
fits share photons and are not independent observations.

Across all specified Te/ne cells, nominal-resolution central ionic logarithms
span **1.380–1.871 dex**; generic point LSF gives **1.395–1.830 dex**. These are
deterministic grid sensitivity ranges, **not confidence intervals**. Formal
Fieller sets at every cell are saved in `research_output/mom_ionic_fit.json`.
The published separate ionic calculation in Naidu et al. v2 §3.2.3 reports a
roughly 1.3–1.7 dex solar-relative range from a different measured flux/model
treatment. Agreement in scale does not make either calculation model independent.

If `fN` and `fC` are the fractions of nitrogen and carbon in the two observed
stages under the common-zone assumption, the elemental result is
`(N/C)_elemental = (N/C)_ionic * fC/fN`. Neither fraction is measured here.
An arbitrary stage-fraction multiplier can change the elemental abundance while
preserving these four line fluxes. Consequently this analysis supplies **no
elemental abundance, polluter likelihood, or galaxy formation discovery**.

## Versioned primary sources and next experiment

- [PyNeb 1.1.32 release](https://pypi.org/project/PyNeb/1.1.32/).
- [Luridiana, Morisset & Shaw 2015: solver and validation](https://arxiv.org/abs/1410.6662).
- [Morisset et al. 2020: atomic-data assessment](https://arxiv.org/abs/2009.10586).
- [Naidu et al. v2 §3.2.3](https://arxiv.org/html/2505.11263v2): its Cue fit
  **excludes N IV]**, which Cue does not emulate; several fitted parameters hit
  the model-grid boundaries. This fact limits calling it a joint five-group fit.
- [Li et al.: Cue photoionization emulator](https://arxiv.org/abs/2405.04598),
  [version v0.1, DOI 10.5281/zenodo.11118643](https://zenodo.org/records/11118643).

Next: fit the accessible four-group Cue predictions using their versioned
weights and full covariance, explicitly retain the N IV] coverage gap, and
compare sensitivity to ionizing-spectrum families and grid edges. Independently
reduced native nod fluxes should replace the old coadd scenarios before any
enrichment comparison is strengthened. Higher-resolution density diagnostics, resolved He II/O III], and resonant-line constraints remain observing needs.

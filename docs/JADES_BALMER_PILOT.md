# JADES Balmer pilot, 12 October 2026

The strongest catalog lead fails a configuration cross-check. No new hydrogen-physics anomaly, galaxy or cosmological discovery is established. The second inspected lead remains weak and unconfirmed. Stop this track pending independently calibrated spectra or an improved conditional likelihood.

## Frozen screen and actual data

Before catalogue download, freeze GOODS-S as discovery and GOODS-N as an unopened outcome holdout. Require robust redshift flag A/B, 2 < z < 7, positive finite 5-pixel Halpha/Hbeta flux/errors, both flux/error >=10 and the same selected grating/filter. Select catalog ratio <2.65 only as a triage threshold. A fixed 2.86 is not a universal physical boundary. No covariance, look-elsewhere calibration or temperature inference follows from catalog diagonal-error scores.

All 5,190 catalog rows are retained in the source. The screen selects 135 GOODS-S observation rows and yields 132 operational sky representatives: group within 0.2 arcsec and retain the largest minimum line SNR without using the ratio. This is not a certification of unique physical galaxies. Eleven representatives have 5-pixel ratio <2.65; seven retain that sign in 3-pixel extraction. One has diagonal threshold score below -3. These counts are not population fractions. Aperture and nod variants share photons. Released configurations share calibration assumptions.

The final code subsets GOODS-S before evaluating any redshift or line outcomes. Initial exploratory code computed outcome masks on complete arrays and only reported GOODS-S; no GOODS-N result was inspected or used. The explicit subset now makes the holdout boundary literal and auditable.

The authoritative public catalogue is https://jades.herts.ac.uk/DR4/Combined_DR4_external_v1.2.1.fits (94,124,160 bytes, SHA256 `4b4e7fd4306208ee801406c7ed73fdab895a2e67184af7f639a91e5f9c8ab7d4`). Documentation: https://jades.herts.ac.uk/DR4/Readme_DR4_catalogues.md and https://jades.herts.ac.uk/DR4/Readme_DR4_spectra.md. Actual FITS labels differ from some README labels; the code uses actual HBaA/HBaB columns. Unique_ID identifies ID/tier, not necessarily a unique physical galaxy.

## Targeted experiments and rejected interpretation

For GOODS-S deepjwst 7496, z=2.493465, catalog G235M Halpha/Hbeta is 1.85324 (5 pixels) and 1.87107 (3 pixels). That apparent aperture stability did not validate the physical interpretation. Catalog PRISM Hbeta=235.82 and blended Halpha+[NII]=770.60 already imply a dust-compatible blended ratio of 3.267.

New fitting of the released 1D coadds uses pixel-integrated Gaussian profiles plus linear continua in fixed +/-0.015 micron isolated-line windows, and a +/-0.02 micron Halpha+[NII] window with fixed [NII] doublet ratio 2.96. Errors are conditional on diagonal supplied coadd errors, without calibration covariance. G140M Hbeta=239.26 +/-10.31, G235M Hbeta=385.89 +/-23.38 and G235M Halpha=652.31 +/-7.54 in 10^-20 erg/s/cm2. The resulting conditional ratios are about 2.73 with G140M Hbeta versus 1.69 with G235M Hbeta. Independent sideband integration obtains about 2.86 versus 1.53: see the independent review, rather than interpreting one fitted ratio as precise calibrated physics.

Hbeta is near the G235M blue edge, whose finite pixels begin at 1.69525 microns. The configuration discrepancy persists in two-nod variants. Edge coincidence is observed; its causal explanation is unproven. This falsifies a robust new physical anomaly from this measurement contract. The released products alone do not establish the exact calibration defect, intrinsic line ratio or source-specific slit transport.

For GOODS-S mediumjwst 8656, z=2.972741, catalog ratio is 2.036 (5 pixels). The same frozen fitting method obtains G235M Hbeta=115.25 +/-14.20 and Halpha=207.73 +/-10.67, ratio~1.80, but only a 2.49 diagonal-score deficit below2.65. G140M Hbeta is weak and highly background/nod sensitive; PRISM Hbeta is also weak. It fails the frozen strong-evidence screen and lacks convincing independent confirmation. Masked/singular or nonconverged fits have null scientific line parameters; optimizer diagnostics are retained separately. Do not interpret those numerical optimizer values as measurements.

The figure is `research_output/jades_balmer_7496_diagnostic.png` (PDF also retained). It displays released spectra and conditional fit results. A temporary plot-input collision between target names was caught during review; target identity is now mandatory in every compact-window key, and a regression test covers it.

## Novelty and portfolio decision

Sub-Case-B Balmer emitters and aperture/calibration issues are already published. Direct priors include McClymont et al., https://arxiv.org/abs/2405.15859; Woodrum et al., https://arxiv.org/abs/2510.00235; Karthikeyan et al., https://arxiv.org/abs/2603.11338; and GHZ1 reduction/extraction checks, https://arxiv.org/html/2609.14574v1. The DR4 paper itself recommends photometric aperture corrections and cautions against different-configuration Balmer ratios: https://arxiv.org/abs/2510.01034. This pilot is a useful falsification, not an established novel finding.

The initial alternative was NEXUS new-epoch line/continuum coupling, anchored to narrow lines, with a genuinely unused epoch held out. The independent [NEXUS feasibility audit](NEXUS_FEASIBILITY.md) subsequently found no demonstrated unused processed epoch at the documented endpoint. This track is stopped, not an immediately executable next priority. Public epoch products: https://nexus-jwst.github.io/updates/ and https://ariel.astro.illinois.edu/nexus/qdr/. Variability existence and spectral variability have already been studied; a new claim requires a new epoch or new predictive constraint. Budget an initial <=60MB/5min targeted spectral pilot. Stop if fewer than three usable epochs or calibration/background effects dominate. Public interest: identifying how early black holes power little red dots.

Third opportunity: use released JADES DR5 MIRI forced photometry with DR4 spectra to test rest-near-IR predictions of stellar versus dense-gas LRD models on a withheld field, after explicit deblending and line-contamination controls. Data and paper: https://jades-survey.github.io/scientists/data.html and https://arxiv.org/abs/2601.15956. A stellar-bump claim itself is already known; novelty would require a model-specific prediction surviving independent coverage. Start with metadata/covered-target count, <=20MB; expand to <=250MB only with a nondegenerate discriminant. Stop if MIRI confusion or absent coverage prevents useful model discrimination. This is an unexecuted opportunity requiring a fresh novelty and data-feasibility gate, not an established next experiment. No acquisition budget is automatically renewed by this proposal.

## Reproduction and scope

Whole public-source hashes, byte counts and URLs live in `research_output/jades_balmer_{catalog,7496,8656}_download.json`. Product body bytes total101,067,840; small HTTP metadata transfers were not fully instrumented. The parent raised the full-catalog budget from50MB to150MB before acquisition; targeted spectra received a separate100MB cap. Catalogue download took21.9s; individual numerical runs took seconds, well below5min. No paid service was used.

Compact `jades_balmer_{7496,8656}_inputs.npz` retain complete released-1D arrays for exact replay. They are released-coadd data, not raw detector exposures or simulated observations. `*_windows.npz` retain plot windows; `*_fits.json` retain source identities and conditional values. The 132-row compact catalogue result retains the screened cohort; reproducing the denominator requires the full source catalogue.

With the research lock and one BLAS thread:

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.jades_balmer_pilot --directory research_output --output /tmp/jades-replay --replay
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.jades_balmer_figure --output research_output
python -m pytest tests/test_jades_balmer_pilot.py -q
```

For fresh public-coadd reproduction, download the catalogue and every source named in the three download manifests to one directory, verify each SHA256 and byte count, then run:

```bash
OPENBLAS_NUM_THREADS=1 python -m tools.jwst.jades_balmer_pilot --directory /tmp/jades-public-inputs --output /tmp/jades-fresh
```

This reacquires released products and repeats analysis; it does not reproduce the original JADES reduction. Four focused tests cover target-key identity, masked-data availability, absent-line uncertainty and independent numerical-quadrature injection normalization. Independent catalog and spectral review pointers are in `RESEARCH3_JADES_INDEPENDENT_REVIEW.md`.

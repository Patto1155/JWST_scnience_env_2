# Independent JADES DR4 Balmer audit

**Decision: the strongest catalogue outlier is a defensible configuration-discrepancy lead, not a validated astrophysical Balmer anomaly. No GOODS-N outcome rows were examined.** The audit CLI takes explicit `--data-root` and `--output-root` paths. Input names are relative to the supplied data root.

## Catalogue reproduction

`discovery.research3_jades_catalog_review` reproduces the frozen GOODS-S selection independently: **135 observation rows, 132 sky representatives, 11 Halpha/Hbeta < 2.65, seven below 2.65 in both extraction widths, one diagonal threshold residual < -3**. It exactly matches the original pilot's retained catalogue indices. Fluxes and errors have FITS units `10**-20 erg s-1 cm-2`; R1000 columns describe separate Halpha and [NII], unlike the prism Halpha complex.

Three near pairs account for all sky deduplication; each also shares a positive DR5 source ID and consistent robust redshift. No selected positive-DR5 repeat lies beyond the declared 0.2 arcsec radius. The greedy suppression happens to agree with pair grouping here; it is not generally a connected-component algorithm. The 132 representatives are an operational count, not certified unique galaxies. Selecting only high-SNR representatives can condition the ratio distribution; this targeted catalogue cannot estimate prevalence or completeness.

The filter columns sometimes contain literal `b'...'` strings. Canonicalizing these adds zero eligible same-configuration observations. Stored SNR is an `(N,1)` FITS field and must be reshaped before comparisons; all selected observations also have stored SNR >= 10. The frozen selection correctly uses explicit flux/error, which differs modestly from stored SNR.

## Strongest catalogue lead

`goods-s-deepjwst_7496`, A-quality z = 2.49346534798, RA 53.0670414 deg, Dec -27.8989151 deg: catalogue ratios **1.85324 (5 pixels), 1.87107 (3 pixels)**. No other GOODS-S target lies within one arcsec or shares its positive DR5 ID. Apertures and nod choices share photons and are sensitivity checks, not replication.

The diagonal threshold score is -6.770. Allowing any valid Halpha/Hbeta correlation while holding the catalogue marginal errors fixed bounds that score between -5.760 and -8.607. Correlation alone cannot remove this formal discrepancy, but incorrect marginal errors, calibration, extraction and modelling systematics can. Reaching 2.65 needs a 42.99% Halpha increase or 30.07% Hbeta decrease. These are diagnostic calculations, not calibrated significance or a physical impossibility claim; 2.65 is a frozen screen, not a universal atomic bound.

## Actual-spectrum independent oracle

`discovery.research3_jades_spectrum_review` uses direct flux-density box integration and a constant continuum fitted from a red sideband. It imports no candidate-fitting code and uses no Gaussian model. It verifies RA/DEC, TARGET, tier, micron wavelength and per-Angstrom flux units in both released x1d files and pins SHA256 hashes. Boxes of half-width 0.0025, 0.0035 and 0.0045 micron are post-triage sensitivity checks. Missing bins are not filled; coverage fractions are reported. Formal errors assume diagonal spectrum errors and include continuum-estimation variance.

For the **5-pixel, 3-nod, +/-0.0035 micron** box, fluxes in `1e-20 erg s-1 cm-2` are:

| Measurement | Direct integration | Conditional diagonal error |
|---|---:|---:|
| Hbeta, G140M | 225.23 | 19.14 |
| Hbeta, G235M | 420.50 | 25.94 |
| Halpha, G235M | 645.05 | 9.39 |

This gives Halpha/Hbeta **2.864 using G140M Hbeta**, versus **1.534 using G235M Hbeta**. Across the three boxes, 5-pixel 3-nod ratios using G140M Hbeta span 2.754–2.864, whereas G235M-based ratios span 1.452–1.656. The 3-pixel and 2-nod diagnostics preserve the strong configuration discrepancy. Boxes are deliberately not optimized or promoted into independent significance tests; wide Halpha windows may include [NII] wings.

These independent results support `tools.jwst.jades_balmer_pilot`'s Gaussian finding (G140M Hbeta 239.26 vs G235M 385.89; G235M Halpha 652.31), although individual box and Gaussian fluxes need not agree because continuum/line treatments differ. Both methods remove the supposed low-decrement anomaly when using G140M Hbeta. They do not certify G140M as unbiased or establish the object's true intrinsic decrement.

G235M 5-pixel finite coverage begins at 1.69524994 micron, only 0.00351047 micron blueward of the redshift-predicted vacuum Hbeta wavelength 1.69876041 micron. The Gaussian fitted center differs slightly from that prediction. The proximity is verified; **it does not prove that edge calibration caused the disagreement**, exclude spatial contamination, or identify the correct correction. Released products assume point-source slit-loss corrections. Both gratings combine observations spanning January 2024–January 2025, so detailed exposure-level provenance is needed before claims about independent visits or variability.

## Second candidate 8656

A separate direct-integration check verifies the released headers for `goods-s-mediumjwst_8656`. The 5-pixel 3-nod +/-0.0035 micron box gives Hbeta G140M 144.96 +/- 90.51, Hbeta G235M 108.37 +/- 22.22, and Halpha G235M 208.30 +/- 14.41, in the same flux units. G140M Hbeta is weak and changes substantially in the 2-nod diagnostic (31.24 +/- 83.49), so it cannot independently resolve the decrement. The author Gaussian Ha/Hb = 1.802 has a conditional diagonal threshold contrast of -2.498, below the frozen 3-unit threshold; it remains tentative.

The expected G140M Hgamma wavelength is 1.7248370 micron, with zero finite bins within +/-0.001 micron and the nearest finite bin 0.0015637 micron away. The author fit Jacobian has rank 2 for five parameters. Its scientific line parameters are unidentifiable; a pseudo-inverse error of zero would be invalid. The final repository outputs were independently parsed with strict JSON handling: all rank-deficient, boundary or nonconverged scientific flux, error, center, width and NII fields are null, with numerical optimizer diagnostics separated. Hgamma remains unidentifiable; it is not a zero-error non-detection.

## Novelty and permissible claim

Generic JADES sub-Case-B Balmer decrements are already published: Yanagisawa et al. 2024, arXiv:2403.20118v2, and McClymont et al. 2025, MNRAS 540, 190. The first explicitly investigates GS-NDG-9422/RXCJ2248-ID and non-Case-B radiative-transfer mechanisms; the latter surveys anomalous JADES objects. A search for JADES target 7496 did not establish prior treatment, which does not certify novelty. A source-specific configuration inconsistency or a validated new selection/model effect could justify further work. This audit supports no discovery of new hydrogen physics, revised dust law, ionizing escape fraction, cosmology, or population prevalence.

Primary release documentation checked directly:
- https://jades.herts.ac.uk/DR4/Readme_DR4_catalogues.md
- https://jades.herts.ac.uk/DR4/Readme_DR4_spectra.md
- https://arxiv.org/abs/2403.20118
- https://academic.oup.com/mnras/article/540/1/190/8126735

## Reproduce

Run with a Python environment containing numpy and astropy:

```bash
python -m discovery.research3_jades_review catalogue --data-root /path/to/pilot --reference-root data_sources/research3/audit/frozen_inputs --output-root /path/to/review
python -m discovery.research3_jades_review spectrum --source-id 7496 --data-root /path/to/pilot --output-root /path/to/review
```

Receipts: `data_sources/research3/audit/independent-review-receipt.json`, `independent-spectrum7496-receipt.json`, and `independent-spectrum8656-receipt.json`. The catalogue audit references archived frozen pilot inputs with exact hashes. The spectrum command also accepts `--source-id 8656`. These are bounded operator review evidence, not release-facing discoveries.

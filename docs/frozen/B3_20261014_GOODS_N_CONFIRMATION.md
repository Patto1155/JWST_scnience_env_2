# Agent B single GOODS-N confirmation — 14 October 2026

GS training result and numerical prediction committed4fbf419. Only then
metadata HEAD resolved the official GN-only DR4 v1.2 catalogue (33,471,360bytes),
linked as GOODS-N clear/prism/gratings catalogue on official MAST JADES page.
No GN outcome accessed before this prospective commit. GS fallback is therefore
not applicable; GS heldout spectra stay unopened. This is one GN confirmation
experiment; multiple required product transfers are not repeated tests.

Use the exact GN catalogue URL in b_northern_metadata_gate.json. Apply the same
B selection algorithm, lines, S/N5--30, configuration, wavelength, PCG64 seed
20261014 and sorted identities, require30eligible; fixed first15selected rows
are the sole confirmation sample. No outcome-based replacements, same marginal
operator/nuisance assumptions, >=12usable. Commit GN selected identities before
its spectra. Only B opens them. Do not use GN to tune offset/width priors or
select another estimator. Remaining GS heldout is not additional confirmation.

Test the committed N(0,1) descriptive prediction once using mean/SD and KS;
also report the frozen empirical GS-pull prediction. Field/selection/estimator
mismatch and unknown shared-photon covariance still block catalogue-error-scale
identification and spectroscopy validation. Population cumulative300MB cap
includes both catalogues, every spectrum and failures. Disk floor unchanged.

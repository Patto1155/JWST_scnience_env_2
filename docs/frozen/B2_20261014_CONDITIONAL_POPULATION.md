# B2 conditional population estimator agreement — 14 October 2026

Root authorizes this separate conditional scope before catalogue/spectra GET.
B raw prior/source-operator prerequisites remain unmet; this is no raw validation.
The B frozen sample, lines, seed, S/N, split, budget and tests stay unchanged.

Published RUBIES arXiv:2409.05948v2 §3.3/Fig9 reports slit-edge wavelength
shift bounded by approximately one detector pixel (two-pixel shutter) and a
mean PRISM/G395M systematic +0.25 pixel. Neither is a measured population sigma.
Use a deliberately conditional transported geometric sensitivity prior:
u~Uniform[-1,+1] detector pixel, common delta=-0.25+u pixel. This distribution
and application to medium-grating JADES released wavelengths are ASSUMPTIONS,
not empirically calibrated offsets. No replacement wavecorr.

For each line window, integrate over 41 Gauss-Legendre u nodes and 41 uniformly
weighted Gaussian-width nodes between 0.2 and 3 median wavelength bins. Shift
centroid by delta*median wavelength bin (local linear wavelength mapping).
At each node fit signed integrated Gaussian plus linear continuum by weighted
least squares with supplied diagonal errors. Properly marginalize continuum/
flux with Gaussian determinant weight, then marginalize shift and width;
report signed mixture mean and variance, preserving between-node variance.
The local linear mapping is another declared approximation. Width uniform
prior is finite and explicit. Linear-parameter prior is flat in the same
fixed units for all nodes. This operator differs from JADES fitting, and
published redshift reuses the same photons. No claim of noise calibration.

Window +/-0.015 um, finite positive errors, >=8 bins, full-rank linear design,
>=12 usable training/heldout rows. No replacement for failure. Catalogue read
selects published S/N as frozen (selection on published outcomes explicitly
permitted); chosen identities commit before spectra access. Download only
training spectra before training result and confirmation prediction commit.
If a source appears in both halves, omit its heldout test rather than reuse
its photons; retain omission in denominator. Preserve all failures. No northern
spectra/catalogue until root's confirmation protocol prerequisites. A frozen
GOODS-S heldout test is acceptable if no applicable GN catalogue demonstrated.

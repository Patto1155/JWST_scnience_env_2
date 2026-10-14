# C2: separately prospective current-release known-answer

C1's original-v1 spectrum cannot be resolved at the tested public endpoints;
its immutable design50a711a remains blocked, not edited or rescued. MAST metadata
now lists the current v2.0 products, but no spectrum or catalogue outcome has
been opened/downloaded. Coordinator authorizes this separate experiment.

Target remains GOODS-S NIRSpec_ID10058975, goods-s-deephst, RA53.11243,
DEC-27.77461. Hypothesis: the current published DR4 [O III]5007 line flux/error
can be recovered from that released current G395M/F290LP v2.0 spectrum. Public
DR4 PaperII (arXiv2510.01034) provides the line-flux catalogue with quoted errors;
use official MAST GS-only v1.2 catalogue, never combined GS/GN or GOODS-N files.
Select that exact target/tier by identity metadata before reading its line
outcome; R1000_5pix row is the sole primary reference. No selection on flux,SNR,
ratio,residual,or best-configuration agreement. If the chosen line's declared
configuration differs from G395M/F290LP, record mismatch and stop primary test.

Fit the exact same fixed operator as C1: vacuum5008.24A, catalogue's fixed
z_Spec for this exact row (published redshift, not freely optimized),+/-0.015um,
5-pixel FLUX/FLUX_ERR, signed pixel-integrated Gaussian+linear continuum,
center offset+/-0.003um,sigma0.2--3medianbins. Finite positiveerrors only.
Catalogue primary column O3_5007_flux and corresponding _flux_err (resolve exact
published spelling by metadata, record it). Primary delta=(recovered-catalogue)
/catalogue quoted error; PASS1σ/2σ iff abs(delta)<=1/2 and full-rank converged
nonboundary fit. Shared-photon combined error is descriptive, never independent
corroboration. One target,line,aperture,configuration; no multiplicity correction.
Null: dimensional/operator recovery agrees with this published reduction's
quoted uncertainty. Neither success nor failure verifies MoM source calibration
or error coverage. C1 Table3 original35.8+/-0.8 comparison is secondary and
explicitly release-mismatched, never a substitute primary success criterion.

If a public original/current s2d has an identifiable documented five-row spatial
extraction and point-source/pathloss factor, apply that operator once, retain
recovered-flux comparison and name all assumptions. If not, do not manufacture
an extraction aperture/correction chosen after viewing outputs; retain the
blocked2D extraction and unexecuted raw detector chain. Complete raw acquisition
must fit the remaining300MB cap; an incomplete detector chain never passes.

Primary data URLs are the exact MAST-returned v2.0 GS-deephst10058975 G395M
x1d642240bytes/s2d1938240bytes and GS-only catalogue:
https://archive.stsci.edu/hlsps/jades/dr4/goods-s/catalogs/hlsp_jades_jwst_nirspec_goods-s_clear-prism-gratings-line-fluxes_v1.2_catalog.fits
Data and metadata body totals combine C1+C2 (science<=300,000,000bytes,
metadata<=30,000,000bytes). Preserve status,URL,identity,actualbytes,hash/time,
failedbodies. Delete raw files after compact reduction,never commit. Do not
edit this design after access. Outputs docs/KNOWN_ANSWER_TEST.md and
research_output/session_20261014/c_*; acceptance focused pytest plus replayCLI.
No GOODS-N,grades,statefileedits,push/merge. List notrun,notverified,freezehash
and firstoutcomeacquisitiontimestamp. Future prospective tests need new designs.

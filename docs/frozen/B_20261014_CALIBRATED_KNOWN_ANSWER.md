# B: prospective raw and population recovery — 14 October 2026

Freeze this file in a git commit before any new scientific product/catalogue
GET. Historical C2 outcomes are known and are never blind confirmation.

## Raw primary

Fixed JADES GOODS-S target NIRSpec_ID 10058975, goods-s-deephst,
RA 53.112434 deg, DEC -27.774609 deg, G395M/F290LP, vacuum [O III]
5008.24 Angstrom. Reference: DR4 R1000_5pix catalogue row; exact v1.2 GS-only
catalogue and v2.0 product identifiers as c2_acquisition.json. No replacement.
Metadata must resolve every RATE/CAL contributor, target/slit identity, five-row
extraction and pathloss operator, references and body lengths before acquisition.
Reduce original products through this repository's native operator; do not
substitute a released-1D fit. A partial chain or an unresolved operator is BLOCKED.
Raw/reference cap 1,073,741,824 bytes, disk floor 5,000,000,000 bytes.

The wavelength zero-point is a nuisance, never a replacement CRDS wavecorr.
Before science access, derive its prior from a published quantitative NIRSpec
MOS slit-centring-offset measurement appropriate to this grating. Retain source,
quoted units, mapping to wavelength and prior parameters in a separate committed
prerequisite amendment. Do not equate prism/grating redshift discrepancies with
MOS centring scatter or invent a numeric Gaussian width. If quantitative source
or mapping cannot be established, stop the marginalised measurement. Integrate
likelihood over the committed prior rather than selecting its best offset.

Primary recovery criterion: |measured-published|/hypot(sigma_measured,
sigma_published)<2, with converged identifiable fit and nuisance included.
This is the user-authorized descriptive recovery contract, not independent
coverage certification. One target/line means one test. A failure or unresolved
raw chain leaves all spectroscopy at/below Unconfirmed lead.

## Population primary and sealed confirmation

Fresh science counter 300,000,000 bytes including catalogue and all spectra.
Before spectra, select 30 distinct GOODS-S source-line rows, RNG seed 20261014,
NumPy PCG64, from R1000_5pix, lines O3_5007, Hb, Hg. These isolated features
avoid the Halpha+[NII] blend. Eligible catalogue rows require GS identity,
finite z>0, finite positive flux/error, quoted 5<=S/N<=30, a medium grating
configuration g140m_f070lp/g140m_f100lp/g235m_f170lp/g395m_f290lp, and
observed line wavelength within 0.7--5.3 um. Sort by Unique_ID then frozen
line-list order before sampling without replacement. Freeze chosen identities
and their deterministic seeded permutation before downloading spectra; no
replacement after a failed fit. Require at least 30 eligible rows or stop.
Same objects may contribute multiple lines; retain grouping in uncertainty.

First 15 sampled rows are GOODS-S training; final 15 are held out. Keep held-out
spectra/results unopened until the training result and numerical prediction
are committed. Fit signed pixel-integrated Gaussian plus linear continuum,
+/-0.015 um, supplied FLUX/FLUX_ERR, EXTRACT5PIX1D, as fit_line. The same
quantitative-prior prerequisite blocks nuisance-marginalised population claims.

Compute signed combined-error pulls, sample mean/SD, normal QQ summaries,
KS comparison to N(0,1) (diagnostic only). Require >=12 usable training rows;
report invalid/absent fits in the denominator. A broad distribution indicates
estimator disagreement; it cannot uniquely diagnose underestimated published
errors: Var(F1-F2)=Var(F1)+Var(F2)-2Cov(F1,F2), and both estimators reuse photons.
Report pull-width scale as descriptive, never an inferred published-error
multiplier absent an independent covariance model and operator-bias controls.
S/N-truncated catalogue selection also prevents a universal coverage claim.

Before any GOODS-N outcome, commit GS training results plus numerical predicted
mean=0 and SD=1 under the descriptive reference; 95% mean interval
+/-1.96/sqrt(n), SD acceptance from chi-square 2.5/97.5 percentiles with n-1 df.
Only B may metadata-check existence of an applicable independent northern line
catalogue after this commit. If absent, retain GOODS-N sealed and open the frozen
GS held-out half. Raw prerequisites failing do not become a population/raw pass.

## Controls and delivery

Dimension/operator synthetic controls test implementation, not sky calibration.
No promotion without actual null, injection, independent-repeat artifacts.
Record UTC, URL, method, status, bytes, hash, cap and disk floor per access;
charge failed bodies, preserve missing lengths as unknown, delete raw products.
Metadata HEAD/body requests precede expensive products. Outputs
CALIBRATED_KNOWN_ANSWER.md, b_* compact receipts. Focused pytest plus explicit
historical replay; root owns full gate and state. List not run. No state edits,
no GOODS-N before the confirmation prerequisites, no merge.

# Research 5: CLASS–DESI coronal-line event pilot

Status: metadata feasibility verified; frozen before spectrum retrieval on
2026-10-12. This is an exploratory object-specific event search, not a discovery.
Coordinator authorized a 300,000,000-byte pilot. No GOODS-N products are used.

## Sources and novelty scope

CLASS: Reefe et al. 2023, ApJS 265,21,
https://cdsarc.cds.unistra.fr/ftp/J/ApJS/265/21/ReadMe and
https://vizier.cds.unistra.fr/viz-bin/asu-tsv, source
`J/ApJS/265/21/catalog`, `Ndet=>=2`. The actual 15,502-byte response contains
131 rows, including nine Kewley-2001 non-AGN classifications. The public
SPARCL production API is https://astrosparcl.datalab.noirlab.edu/api/;
version 14.2 returned HTTP 200. All 131 positional metadata queries succeeded,
transferring 176,783 response-body bytes: 51 rows have SDSS and DESI-DR1;
40 rows have both baseline Fe VII 6087 and 5720 luminosities. These are rows,
not deduplicated galaxies. The square retrieval region is only a candidate
lookup: each claimed identity requires angular separation <1 arcsec and
redshift agreement |delta z|<0.001.

Broad changing-look searches are already mined (Guo et al. 2024/2025 and
recent high-z DESI–SDSS catalogs). Coordinated iron fading itself is known.
This pilot's possible added result is a new event in a particular CLASS object,
conditional on verified spectra and independent second-line/epoch evidence.
Known ECLEs from Callow/Clark 2024–2026 and Kynoch et al. 2026
https://arxiv.org/html/2606.04090v2 must be excluded from a new-event claim.
The last paper explicitly compiles 33 sources. Its table does not include
the selected object; this is a concrete catalog exclusion, not exhaustive
novelty certification. Exact-coordinate/target-ID searches returned no results;
their absence supplies no novelty proof.

## Frozen selected object and epochs

SDSS J111855.13+514847.2: RA 169.72972, Dec 51.81310, baseline z=0.08007.
SDSS plate 878, MJD 52353, fiber 545; CLASS Ndet=2, K01AGN=false,
log stellar mass=10.324, log L(Fe VII 6087)=40.071,
log L(Fe VII 5720)=39.308 [erg/s]. It is not a dwarf-galaxy claim.
J110419.21+154508.3 has stronger baseline lines but no public DESI match;
it is stopped for availability. No other cohort outcomes may be opened here.

| Product | SPARCL UUID | Center date |
|---|---|---|
| SDSS-DR17 | 27a4e980-5e21-11f0-9aca-525400f334e1 | 2002-03-20 |
| DESI-DR1 | 2bf205a7-87cb-11ef-8f00-525400f334e1 | 2021-01-17 |
| DESI-DR1 | a6d1bcbc-885a-11ef-bbe3-525400f334e1 | 2021-03-25 |
| DESI-DR1 | 6acc3cce-884f-11ef-9a35-525400f334e1 | 2022-02-19 |

All three DESI products have target ID 39633274733070169 and redshift warning
zero. EDR January/March records repeat the same center dates and are excluded
as independent epochs. Center dates alone do not establish disjoint photons:
retrieve `file`, `extra_files`, `survey`, `exptime`, and native exposure metadata
before treating the three DESI products as independent.

## Frozen measurement and decision contract

Discovery line is Fe VII air label 6087 (vacuum center approximately 6088.64 A).
Confirmation line Fe VII air label 5720 (vacuum approximately 5722.29 A) remains
unopened by this author until discovery-line results pass their gate. Independent
reviewer owns confirmation interpretation. Both datasets use vacuum wavelengths.
Fix systemic z=0.08006536215543747 from SDSS metadata; test delta z +/-0.00010
as a sensitivity calculation, never as an optimized rescue.

For each line use direct inverse-variance weighted linear sideband continuum,
rest-frame sidebands center+[-40,-20] and [+20,+40] A, and integrate within
center +/-8 A. Propagate pixel plus fitted-continuum uncertainty. Exclude
observed vacuum 6564.61 +/-4 A (geocoronal H alpha) from every integration
window; never interpolate excluded pixels. Require at least 90% finite,
positive-IVAR, unmasked wavelength width AFTER the fixed sky exclusion and
adequate samples in both
sidebands; report unavailable measurements and original-box sky-excluded width
separately. These are partial line fluxes, without extrapolation. Repeat
using +/-12 and +/-16 A windows and sidebands [-60,-30],[30,60] A. Use local
narrow controls [O I]6302.05 and [S II]6718.29,6732.67 A (vacuum); sum the sulfur
doublet. Control ratios must agree within 20% after an overall amplitude scale,
with adequate S/N>10. [O III]5008.24 supplies a separated diagnostic, not a
guaranteed constant normalization. No Fe X endpoint is used, avoiding the
[O I]6364 deblend ambiguity.

Gate: baseline discovery-line S/N>=5; either coordinated decrease by factor>=3
relative to both local controls between SDSS and earliest DESI, with propagated
contrast significance>=5 sigma, or same-facility DESI change by factor>=3 at
>=5 sigma between verified disjoint-photon epochs. The earliest DESI contrast
is primary; later DESI products assess repeatability, not optimized epoch choice.
For nondetections compare conservative 3-sigma upper bounds rather than zeros.
If gate passes, open confirmation: independent 5720 measurement must support
the same-direction factor>=3 contrast using a conservative 3-sigma upper bound
and baseline S/N>=5. Failure of the weak confirmation line's power is a stop,
not evidence of coordinated fading. Require sign and factor threshold to survive
all window/continuum variants. Only one object and one discovery endpoint are
tested; baseline selection can overestimate apparent declines and must be
stated. No population incidence inference is permitted.

Unequal SDSS 3-arcsec and DESI 1.5-arcsec fibers remain an astrophysical aperture
alternative even if narrow controls agree. A repeated DESI contrast can reject
that specific alternative only after exposure provenance and centering checks.
Otherwise the strongest valid result is a conditional, aperture-normalized
coronal contrast, not a uniquely intrinsic flare or a confirmed TDE.

Pre-outcome amendment: independent reviewer accepted the fixed geocoronal
exclusion and +/-8 A primary window before any spectrum retrieval. API dateobs
ranges verify sv1 2021-01-02 through 2021-02-01, sv2 2021-03-25, and main
2022-02-19 are disjoint; native provenance remains useful additional validation.
Formal significance from pixel IVAR is conditional on unmodeled resampling
covariance; it is not automatically a calibrated astrophysical false-alarm rate.

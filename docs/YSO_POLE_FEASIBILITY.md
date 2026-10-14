# Pole-field YSO metadata feasibility — 2026-10-14

**The metadata gate is not established. All three northern targets fail the
frozen visit requirement; southern source coverage and six catalogue K
associations remain unresolved. No science pilot is authorized by this evidence.**

The prospective design was committed as `264a875` before first identity/archive
access. Agent A's allowance amendment is inherited as `c8ff9f6`. No outcome
spectra, pixels, WCS array ranges, lightcurves or science-product bodies were
retrieved. No state file or scientific grade is edited.

## Fixed sample and exact inventory

SIMBAD's frozen pole cones returned three North and ten South catalogue YSO
identities. Both `spherex_qr2_deep` and `spherex_qr3_deep` were queried. Every
successful QR3_deep query returned no rows; QR2_deep supplied the counts below.
Release identity is deduplicated by (obs_id, detector). The bin is floor(MJD),
fixed before access. Day/exposure counts are **not certified same-wavelength
visits**. Unknown source coverage is retained, never treated as zero flux.

| Catalogue identity | Pole | Physical detector exposures | UTC-day bins | Max frames/day | Upper bound eligible days | 2MASS K |
|---|---|---:|---:|---:|---:|---:|
| 2MASS J19382481+7003455 | north | 56 | 18 | 7 | 0 | 12.555 |
| UCAC4 800-028207 | north | 27 | 10 | 4 | 0 | 11.058 |
| 2MASS J19420738+6816508 | north | 27 | 10 | 4 | 0 | 12.055 |
| 2MASS J05475106-6629071 | south | 711 | 81 | 31 | 44 | 14.072 |
| 2MASS J05454478-6709283 | south | 774 | 80 | 30 | 42 | 14.124 |
| [GC2009] J054624.75-671916.5 | south | 757 | 80 | 30 | 42 | absent |
| [GC2009] J054442.25-661733.5 | south | 804 | 104 | 29 | 44 | absent |
| OGLE LMC-ECL-37636 | south | 825 | 109 | 29 | 44 | absent |
| 2MASS J05463258-6725244 | south | 758 | 80 | 30 | 42 | 12.202 |
| [GC2009] J054445.26-670856.9 | south | 791 | 82 | 31 | 43 | absent |
| 2MASS J05551099-6806234 | south | 661 | 74 | 27 | 37 | 15.11 |
| [GC2009] J054447.39-671631.8 | south | 808 | 81 | 30 | 44 | absent |
| [WSI2008] 1124 | south | 808 | 81 | 30 | 44 | absent |

All three northern sources have fewer than eight frames in every day, and thus
cannot supply the frozen eight source channels per visit. Six southern sources
lack SIMBAD K cells; this is missing catalogue metadata, not proof that they
lack 2MASS counterparts or are intrinsically unusable. Four southern targets
have assignable K in the first catalogue. The true metadata upper bound remains
ten potentially qualifying southern sources; source-wavelength eligibility and
matched-control eligibility are not established for any of them.

A preliminary four-target impossibility interpretation was withdrawn during
lead review before integration. The corrected offline reducer and its regression
test preserve unknown K targets as potentially feasible. The subsequent
committed `722803e` amendment fixed a1arcsec unique2MASS association screen
before official catalogue access. Initial TAP calls returned three504responses
and three empty results. The official Gator endpoint subsequently returned zero
2MASS PSC matches for **all six** selected objects within that fixed1arcsec
cone. An initial local IPAC-table parser error was corrected; both failed parses
and repeated bodies remain charged. No K magnitude was imputed, no association
radius expanded, and no target replaced. These six catalogue associations remain
unresolved under this bounded screen; wider associations/alternative catalogues
were not examined. This is not proof of physical absence of infrared light.

This arm stops science acquisition because the five-target eligibility gate is
not demonstrated by metadata, retaining source-channel coverage as unknown.
North visit-count failures are fully determined. South is not a scientific null
or rejected population; only four targets currently have known K for the exact
frozen control match, and their wavelength/control coverage also remains unknown.

Corrected northern control queries returned 0,5,5 potential main-type normal
stars respectively; corrected queries for the first two southern sources and
J05463258 returned five each. Same-field spectral coverage, alternate variable
class associations and empirical constancy are **not certified**. Controls for
J05551099 were not rerun after its initial ADQL alias error because source coverage remains unqualified and no science acquisition can
follow. This is a not-run item, not a proof of absent controls.

## Primary sources and premise corrections

- [Official mission](https://spherex.caltech.edu/) states that the South deep map
  is shifted to avoid the LMC. Pole-cone proximity alone is not deep membership;
  actual deep-collection rows above provide the required pointing inventory.
- [IRSA data-access documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
  identifies separate QR2/QR3 deep collections. [IRSA instrument overview](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/overview.html)
  explains that full spectral coverage is assembled over multiple pointings.
  The premise that 0.75--5 microns is measured at once in one exposure is false.
- The `[GC2009]` identities trace to [Gruendl & Chu 2009](https://arxiv.org/abs/0908.0347),
  ApJS184,172, a published LMC YSO-candidate catalogue; `[WSI2008]` traces to
  [Whitney et al. 2008](https://doi.org/10.1088/0004-6256/136/1/18).
  SIMBAD coordinate bibcodes in the receipts include Gaia/2MASS astrometry and
  do not themselves confirm youth. Individual spectroscopic classification,
  brightness adequacy for SPHEREx, blending and ice absorption are not verified;
  this additional qualification could only reduce the possible sample.
- [Leinert et al. 2001](https://arxiv.org/abs/astro-ph/0102042) already measured
  temporal 3.1-micron water-ice absorption in Haro6-10 over23 observations
  (1988--2000), reporting variability at3.5sigma(S) and2.0sigma(N). An ice-band
  variability result is not inherently a first detection.
- [Kim et al. 2026](https://arxiv.org/html/2604.08769v1), EPISODEIV, compares
  EC53's JWST burst/quiescent spectra and reports no measurable change in its
  ice bands after continuum/silicate modeling. The field has a useful measured
  null as well as prior variable absorption. This is a bounded literature check,
  not an exhaustive priority/novelty audit.

## Reproduction and accounting

```
python -m discovery.research7_yso_poles --summarize-only research_output/calibrated_20261014/e_poles_final/e_summary.json.gz
python -m discovery.research7_yso_poles --timeout 12 --out /tmp/new_pole_metadata
python -m pytest -q tests/test_research7_yso_poles.py tests/test_research6_yso_pilot.py tests/test_research5_spherex_review.py
python -m ruff check discovery/research7_yso_poles.py tests/test_research7_yso_poles.py
```

First command is offline and creates `e_necessary_gate.json`. The byte-exact
metadata replay is deterministically gzip-packaged (`mtime=0`);
`e_summary_packaging_receipt.json` records both compressed and uncompressed
SHA256 hashes. Packaging does not change acquisition accounting or outcomes. The second makes
new queries; archive ingestion may change inventory. Initial HTTP400 requests
are retained and charged. They resulted from ADQL ORDERBY syntax and a reserved
alias, corrected without changing selection. Executed code hashes bind each
inventory; source commits preserve the original executions. Formatting and an
offline necessary-condition and unknown-metadata reducer were added subsequently.

Direct HTTP metadata bodies, including failed responses and diagnostic retries:
**7,261,777 bytes**, below30,000,000. Science products: **0 bytes**.

`e_budget_manifest.json` lists every charged receipt. Web search/source-document
tools do not expose transport-body byte counts and are explicitly excluded from
the certified direct HTTP subtotal; this is not a certified total of all tool
network traffic. Disk free was25,031,516,160 bytes before acquisition, above5GB.
Raw metadata CSV/error bodies were reduced/discarded; retained products are
compact identity/exposure reductions and receipts.

Not run: source wavelength/width or PSF/support tests; science flux/ERR arrays;
photometry; ice-band change statistic; field-star empirical null; injection
recovery; independent-repeat science measurement; GOODS-N; the conditional
500MB pilot. No second science design was frozen because its prerequisite gate
is not established. The existing coarse65,536-byte WCS range reader was not used: those
ranges can overlap IMAGE/ERR bodies despite the historical no_pixels_measured
flag, and are not certified metadata-only accesses.

Final disk-free check:18,620,334,080 bytes, above the5GB floor.

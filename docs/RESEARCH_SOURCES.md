# Verified research sources and acquisition pilot

Inspected 9 October 2026. The machine-readable inventory is
[`data_sources/manifest.json`](../data_sources/manifest.json). This inventory makes
no claim that an image candidate is a discovery or that an abundance model is unique.

## What to use first

| Rank | Pilot | Actual use | What it cannot establish |
|---|---|---|---|
| 1 | Three JADES DR5 `jw011800-deep` F277W/F356W/F444W modeled PSFs, checked in with SHA256 receipts | Inject shapes from a different generator; freeze classifier before evaluation; measure detection, classification, and full-chain recovery separately | Real-stellar generalization or external astrophysical truth |
| 2 | Released JADES DR4 redshift catalogue: acquire once, retain compact references with raw checksum | Match known high-z galaxies, genuine low-z interlopers and ambiguous objects by sky coordinate; blind evaluation | Unbiased population prevalence or completeness of the imaging survey |
| 3 | JWSTSTARS M92 catalogue and matched images (program 1334) | Independent real star morphology across F277W/F444W; quality-based control selection | Immediate transfer across detectors, epochs, crowding and filters |
| 4 | DAWN COSMOS v7.4 cutouts with weights/variance, centered on verified MoM-z14 coordinates | Reproduce selected imaging and quantify coverage | Nitrogen abundance from imaging alone |
| 5 | Individually verified public NIRSpec spectra, using JADES DR4 and DAWN v4.4 | Test line fitting, background/extraction sensitivity and ionization models | Availability of a particular MoM-z14 spectrum solely because its program is public |

The checked-in model PSFs are each 1,800,000 bytes, 669 × 669 pixels, with
`PIXELSCL=0.029994759` arcsec. Their sums are approximately 0.9997, 0.9996 and
0.9995. `BUNIT=MJy/sr` appears in their copied image headers; for injection treat
them as **shape kernels**, normalize the discrete sum, and match sampling to the
image. Do not interpret the model PSF array as an observed source flux.
Full inspected headers and sums are in `data_sources/pilot/psf_inspection.json`.

[JADES DR5](https://slate.ucsc.edu/~brant/jades-dr5/) supersedes earlier imaging
catalogues. Its GOODS-S photometry file is **6,174,754,560 bytes** (observed HTTP
Content-Length), so it is excluded from the bounded pilot. The useful small PSFs
are listed on the team's submosaic directory. These are modeled PSFs, not an
empirical star archive. Cite the
[imaging paper](https://arxiv.org/abs/2601.15954) and
[catalogue paper](https://arxiv.org/abs/2601.15956) for the applicable products.

[JADES DR4](https://jades.herts.ac.uk/DR4/) provides a versioned line/redshift
catalogue and reduced spectra. Checked-in README snapshots explain extraction,
quality flags, null sentinels and units. Spectra offer alternative 2-/3-nod and
3-/5-pixel extraction choices. Point-morphology slit corrections may bias extended
sources. Spectroscopic targeting is selective: a reference sample is a validation
sample, not a representative sample of all objects.

The 94,124,160-byte v1.2.1 catalogue was retrieved once outside the repo; its raw
SHA256 and HTTP receipt accompany the tracked 850,160-byte
`data_sources/pilot/jades_dr4_reference.csv`. It preserves **all 5,190 observation
rows**, with A=2,651, B=207, C=439, D=493, E=1,400. A/B rows include 243 at z≥6
and 1,461 at 0≤z<3. These are observation counts, not distinct galaxies. Match
coordinates and tier+ID, then keep quality and duplicate observation groups visible.
Regenerate using `extract_jades_references(input_fits, output_csv)` from the
acquisition module. Raw catalogues and images remain outside the tracked pilot.

[JWSTSTARS](https://archive.stsci.edu/hlsp/jwststars) is the strongest independent
real-star source. Its M92 imaging uses the two filters of immediate interest plus
F090W/F150W. The released catalogue has DOLPHOT type, SNR, sharpness, crowding and
flags; it has **not been pre-culled**. Magnitudes are Vega, not AB, and quoted
errors reflect Poisson noise only. Exclude the third M92 exposure for excess
astrometric jitter. Catalogue matching must not treat hot pixels/extended types as
stellar truth. MAST specifies CC BY 4.0 and DOI 10.17909/cn6n-xg90. Query metadata
first rather than copying the documentation's unfiltered bulk-download example.

[DAWN API documentation](https://dawn-cph.github.io/dja/general/api_summary/)
provides CSV association/exposure metadata and FITS cutouts with optional inverse
variance extensions. The
[NIRSpec index](https://dawn-cph.github.io/dja/spectroscopy/nirspec/) links public
v4.4 products for program 5224 (`mom-cos03/04/05-v4`). That identifies an accessible
program, **not yet a verified match to MoM-z14**. Match published coordinates,
source ID and redshift, then retain exact extraction/version and checksum. Dynamic
cutouts need receipts because their upstream reduction can change.

## MoM-z14 physics: what is measured and what is inferred

Pin [Naidu et al. v2](https://arxiv.org/html/2505.11263v2), rather than mixing
2025 and 2026 tables. The reported individual UV lines have SNR 2.7–3.4;
`[N/C] = 0.90 (+0.29, -0.63)` dex is inferred through a photoionization model.
The published line table is transcribed in
`data_sources/pilot/mom_z14_published_lines_v2.json`, explicitly labelled as a
transcription rather than a downloaded pixel spectrum. A large ratio is not an
age measurement for the whole galaxy. Background choices, ionization, density,
blends, and tied line width need sensitivity tests before stellar-yield inference.

Three useful competing primary-paper paths:

* [Intermittent starbursts/WR stars](https://arxiv.org/abs/2308.15583): ordinary
  massive-star winds can produce a brief nitrogen-rich phase under particular
  histories. Their GN-z11 scenario includes a roughly 100 Myr hiatus and a very
  short enhanced episode; test time feasibility instead of transplanting it.
* [Very massive stars](https://arxiv.org/abs/2310.10725) and
  [supermassive-star pollution](https://arxiv.org/abs/2601.04344): compare yields
  and retention against WR alternatives. Mass-loss assumptions strongly affect
  the predictions; these are hypotheses, not confirmed populations.
* [Rapidly rotating Population III stars](https://www.aanda.org/articles/aa/abs/2024/08/aa48866-23/aa48866-23.html):
  alternative nitrogen production with explicit rotation and dilution assumptions.
  No numerical downloadable yield grid was verified in this pilot.

Use [CLASSY](https://archive.stsci.edu/hlsp/classy) local UV spectra to test line
fitting and ionization diagnostics before rare high-z applications. Do not infer
that a local analogue has the same stellar demographics as MoM-z14.

## Reproducible bounded access

No network call happens at import or during validation. Select one product before
fetching. The default cap is 5 MiB; response headers and streamed bytes both enforce
it, partial files are removed, existing files are preserved, and completed files
have byte count, SHA256, UTC, final URL, ETag and Last-Modified receipts. An ETag is
not a cryptographic hash. A checksum pins retrieved bytes, not scientific validity.

```bash
python -m data_pipeline.research_sources validate
python -m data_pipeline.research_sources list
python -m data_pipeline.research_sources probe --source jades-dr5-psf --product f444wa
python -m data_pipeline.research_sources fetch --source jades-dr5-psf --product f444wa --output /tmp/f444w-model-psf.fits
```

Use `--max-bytes` only for a deliberately selected larger product. Public-access
status and content may change; re-probe exact links, avoid guessed product URLs,
and record new receipt/version instead of silently replacing a dataset. JADES's
MAST HLSP page states CC BY 4.0 for its HLSP products; DR5 temporary-host licensing
is not stated explicitly, so verify it before broader redistribution. All papers
and data require their relevant scientific acknowledgements.

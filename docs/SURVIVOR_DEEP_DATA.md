# Deep multiband inputs for persistent GOODS hypotheses

The frozen original selection identifies sky hypotheses 98, 254 and 46. Their
source coordinates and the selection CSV SHA256 are retained in the new
[pinned inventory](../data_sources/survivor_deep/manifest.json). These three are
deliberately chosen persistent objects, not a completeness-controlled sample.

On 9 October 2026 the documented
[DAWN cutout API](https://dawn-cph.github.io/dja/general/api_summary/) returned
21 separate science + inverse-variance cutouts: F090W, F115W, F150W, F200W,
F277W, F356W and F444W at each position. Each is about 1.87 MB, 480 by 480 pixels
on a 0.05-arcsec grid, approximately 24 arcsec across. The API `size=12` is
half-width here. Actual FILTER/SCI/WHT identity and WCS center are checked;
file size and SHA256 are pinned independently of mutable local receipts.

Four missing JADES DR5 finite modeled PSFs and seven SVO nominal NIRCam
photon-throughput VOTables were also acquired. Three other modeled PSFs are
reused from the tracked baseline. **New download bytes: 46,932,339.** Full
inventory, including the three reused PSFs: **52,332,339 bytes**, below the
100 MiB aggregate ceiling. Every product also has a streaming byte ceiling.
Large FITS remain outside git; regenerating uses the exact URLs and hashes.

DAWN science is in `10.0*nanoJansky` per output pixel. Its WHT is inverse
variance in stored science units. Header NDRIZIM, CRDS/reduction version,
contributor filenames, WCS and weight maps are preserved in the actual FITS.
For example, source 98 F090W has 48 contributors and 42,431.718 seconds of
header exposure sum. This sum is not certified as each pixel's local depth.
Deep mosaics can include original selection images and other overlapping
cutouts: they are **not independent repeat observations**. Neither the supplied
modeled PSF nor nominal passband is a source-specific empirical calibration.

The next experiment measures signed band fluxes with finite PSF-aware spatial
models, competing morphology/blend assumptions, local background nuisance and
disjoint empirical sky operators. It tests filter-integrated coarse continuum
families without converting their fitted break parameters into redshifts.

## Reproduce

Use the locked research environment from `RESEARCH_PROTOCOL.md`:

```bash
python -m data_pipeline.survivor_deep_data --output /tmp/jwst-deep-survivors
python -m pytest tests/test_survivor_deep_data.py
```

A changed dynamic API snapshot fails closed instead of silently replacing the
documented data version. Pin a reviewed new version if upstream data change.
The acquisition CLI preserves requested/resolved URLs and HTTP provenance
receipts. The checked-in manifest supplies the exact input byte hashes.

Source acknowledgements: [DAWN JWST Archive](https://dawn-cph.github.io/dja/),
[JADES DR5](https://archive.stsci.edu/hlsp/jades), and
[SVO Filter Profile Service](https://svo2.cab.inta-csic.es/theory/fps/).
SVO profiles cite the
[STScI NIRCam filter documentation](https://jwst-docs.stsci.edu/jwst-near-infrared-camera/nircam-instrumentation/nircam-filters)
and identify a photon-counting detector. Raw products stay external; no
redistribution licence is inferred from public access.

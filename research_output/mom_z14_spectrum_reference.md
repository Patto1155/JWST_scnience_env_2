# MoM-z14: verified extracted-spectrum reference

This is a read-only data-quality baseline from the public DJA v4 `PRISM/CLEAR`
extraction, not a redshift or nitrogen-abundance measurement. The analysis uses
the actual FITS binary table, rather than values copied from an article.

The stored `SPEC1D` columns have wavelength in micrometres and flux/error in
microjanskys. Of 473 spectral samples, 467 have a finite positive wavelength,
finite signed flux and a finite positive error. The usable wavelengths span
0.549126–5.495019 µm. Six samples are excluded; overlapping reasons are retained
in the accompanying JSON diagnostic.

The median signed per-bin flux/error is **1.024925**; its maximum is **6.744102**.
There are 55 bins with signed flux/error ≥3. These are **not 55 emission-line
detections**: continuum, bin covariance, extraction systematics and the search
over wavelengths are not modelled here. A descriptive sum of squared bin
flux/error is also recorded, with no p-value or detection-significance claim.

The source-position keys `SRCRA=150.0933255`, `SRCDEC=2.2731627` match the
published MoM-z14 position. `TARG_RA/TARG_DEC` describe the proposal pointing and
must not be used to identify this source. The spatial catalog's redshift
annotation and the paper's fitted redshift are separate evidence; neither is
estimated by this diagnostic.

No additional path-loss or slit-loss correction is applied to stored flux/error.
The next useful scientific work is to assess the extraction's covariance and
continuum, fit the relevant lines with instrumental resolution, and propagate
ionization and stellar-yield assumptions. This diagnostic alone cannot establish
rapid chemical enrichment or discriminate its proposed physical explanations.

## Provenance and reproduction

- Public extraction: <https://s3.amazonaws.com/msaexp-nirspec/extractions/mom-cos04-v4/mom-cos04-v4_prism-clear_5224_277193.spec.fits>
- Manifest product: `mom-z14-spectrum` in `data_sources/manifest.json`.
- Verified SHA256: `42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1`.
- Numerical results: `research_output/mom_z14_spectrum_reference.json`.

Run on the acquired local file (no network or provider API involved):

```bash
python -m tools.jwst.spectroscopy data_sources/pilot/mom_z14_dja_v4.spec.fits \
  --expected-sha256 42d95d348ebb55ca37eb31393b4603628ac13a4bca1f4f7f0ffba7b32d3125b1 \
  --output research_output/mom_z14_spectrum_reference.json
```

Unit/error rejection controls are in `tests/test_spectrum_reference.py`.

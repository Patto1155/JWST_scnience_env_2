# A physical cool-atmosphere prediction for persistent source 46

This follow-up builds on the merged deep-imaging measurement, not a fabricated
source classification. Source 46 is almost pointlike in the adopted F444W
spatial model and has an unusually curved seven-band continuum. The preceding
[image/continuum report](SURVIVOR_DEEP_MODEL.md) found that simple step and
blackbody families fail to reproduce that curve.

We acquired the primary **Sonora Bobcat 2021** synthetic photometry archive,
[version DOI 10.5281/zenodo.5063476](https://zenodo.org/records/5063476), citing
Marley et al., [ApJ DOI 10.3847/1538-4357/ac141d](https://doi.org/10.3847/1538-4357/ac141d).
This is a cloudless, rainout-equilibrium substellar atmosphere family, not a
complete or latest atmosphere library. The archive is **950,605 bytes**, under
a 2 MiB streaming ceiling, and agrees with the published MD5 as well as our
pinned SHA256. [The manifest](../data_sources/survivor_atmosphere/manifest.json)
also pins each actual text-table member and the exact preceding photometry
report version. No large spectral archive or executable author code is needed.

The actual tables declare **log10(flux in mJy) at 10 pc**. We convert their
filter-integrated fluxes to nJy directly, avoiding Vega-magnitude conversion.
Actual filter labels map columns; filenames alone never establish identity.
The apparently JWST-named C/O=1.5 flux file instead has Y/Z/J/H etc. columns;
it is explicitly rejected. Three metallicities (-0.5,0,+0.5) at solar-relative
C/O=1, plus the solar-metallicity C/O=0.5 table, supply **1,052 eligible rows**
at log(g)=3.25–5.5. Author-starred radius fields are preserved as flags, and
lower-gravity rows outside the declared comparison range are excluded.
Independent author-table counts are 273/389/351/39 respectively. One solar
table row at 2401 K lies outside the explicit 200–2400 K selection range;
the earlier prose count included it before that temperature guard was applied.
The saved report and grid CSV already contain the correct 1,052 evaluated rows.

Each tabulated spectrum fits one nonnegative normalization by GLS with the
same complete assumed flux covariance as the preceding 5%/15% floor scenarios.
We retain the top ten rows and seven band-held-out predictions. A held-out
band's flux is not used to choose its grid row or amplitude; the reported
conditional residual removes the assumed shared calibration term. It excludes
model-selection/parameter uncertainty and cannot become a calibrated sigma or
posterior. Finite grid search supplies no continuous confidence region.
The selected source and its F444-derived morphology are reused, so these
held-band checks are not independent imaging or population validation.

## Results and failed predictions

| Assumed independent floor | Best grid chi2 | Simple blackbody chi2 | Best grid parameters |
|---|---:|---:|---|
| 5% | 171.49 | 248.47 | 375 K, log(g)=4.0, [M/H]=-0.5, solar-relative C/O=1 |
| 15% | 49.38 | 89.92 | Same grid row |

These are conditional descriptive comparisons, not equal-complexity evidence
ratios. The best atmosphere row is physically more structured than a blackbody,
but **still fails to reproduce important measured bands**:

| Band | Measured spatial-template flux (nJy) | Best 15% grid prediction (nJy) | Prediction with this band held out (nJy) |
|---|---:|---:|---:|
| F090W | 0.43 | 0.94 | 3.41 |
| F115W | 3.91 | 4.09 | 13.94 |
| F150W | 3.00 | 2.53 | 1.84 |
| F200W | 2.12 | 0.22 | 0.22 |
| F277W | 9.74 | 1.36 | 1.35 |
| F356W | 68.69 | 56.66 | 54.47 |
| F444W | 644.88 | 710.42 | 1474.93 |

In the 15% scenario the omitted F277W prediction leaves a conditional residual
about 5.26 times the assumed conditional error; F200W leaves about 4.04. These
numbers identify useful discrepancy locations, not independently calibrated
rejection probabilities. In particular, a simple foreground cool-object label
does not solve the whole observed curve. Cloud/nonsolar/nonequilibrium families,
multiple objects, morphology/calibration changes and nebular galaxy spectra
remain untested alternatives. The source's physical identity remains unknown.

The best row's normalization would imply about 175 pc **if** it were a single
object with that exact model radius. This is not a distance measurement because
the spectral model is inadequate. That conditional scale provides a testable
foreground prediction: a separately assumed 30 km/s transverse velocity would
give about 36 mas/year of proper motion and an annual parallax about 5.7 mas.
Independent epoch astrometry can test such a hypothesis; hour-scale dither
persistence cannot.

Additional tabulated filter predictions are preserved for forward observing
tests, including F335M/F410M/F430M/F460M/F480M/F770W. They condition on the same
inadequate best row and should not be advertised as unconditional forecasts.
Compare versions/cloud chemistry and physical galaxy SEDs before ranking classes.

## Reproduce

```bash
python -m discovery.survivor_atmosphere \
  --input /tmp/jwst-deep-survivors \
  --photometry-report research_output/survivor_deep_model.json \
  --output /tmp/survivor-atmosphere.json
python -m pytest tests/test_survivor_atmosphere.py
```

The CLI acquires only the pinned sub-MB archive if absent. The
[full result](../research_output/survivor_atmosphere.json) records archive/table/
photometry hashes, rejection reasons, actual grid predictions and all held-out
fits. The [compact grid CSV](../research_output/survivor_atmosphere_grid.csv)
is a versioned numeric derivative with its SHA256 retained in that result.
Four analytic tests verify actual-header identities, unit conversion, author
flags, reordered filters, covariant positive amplitude and an independent
held-out prediction. The embedded author README documents unlimited release
(LA-UR-18-28199) and requests attribution to Marley et al.

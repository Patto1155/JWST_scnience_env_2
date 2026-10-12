# N III/C III observing contrast survives moderate relative-response bounds

The retained finite-model forecast is insensitive to the tested modest errors
in the relative N III/C III response: allowing the ordinary alternative a
50% enhancement in N III relative to C III raises the hardest-pair matched SNR
from 11.315 to 12.540. Allowing the two ion amplitudes to vary independently
raises it to about 13,546. The useful contrast therefore relies mainly on
the physically predicted ratio between ions, rather than their resolved
component shapes. This is a supporting observing-design constraint, **not
a discovery, source calibration, or new abundance measurement**.

## Fixed experiment and result

The prospective [plan](../data_sources/pilot/observation_design/ion_gain_plan.json)
selects N III+C III, nominal G235H, zero intrinsic FWHM, the existing twenty
independently equilibrated Cloudy models and attenuation values 0/0.5/1 mag.
There are no new models, measurements or acquisitions. Each of the 100
enhanced-truth/ordinary-alternative pairs profiles its nine attenuation pairs,
nonnegative overall amplitude, and the declared relative gain. Intrinsic and
emergent responses remain separate. The execution uses the exact reviewed
input SHA256 `7ef48626ddfb7c882d9725b17939c3a7752151de734e3ab4c46472b940127759`.

Truth has unit relative response. For a half-width h the alternative's N III
gain relative to C III may lie in [1-h, 1+h]. This convention is a hypothetical
effective inter-ion response/transfer bound. It is neither independent ±h
uncertainty on both models nor a measured calibration error or a prior.

| Alternative relative-gain freedom | Hardest-pair intrinsic matched total SNR | Hardest-pair emergent matched total SNR |
|---|---:|---:|
| Exact relative response | 11.3146 | 11.3145 |
| ±5% | 11.4260 | 11.4260 |
| ±10% | 11.5397 | 11.5397 |
| ±20% | 11.7743 | 11.7743 |
| ±50% | 12.5398 | 12.5401 |
| Independent nonnegative ion amplitudes | 13,546.5 | 13,557.9 |

The bounded intrinsic cases all select enhanced model009 versus ordinary
model016, truth attenuation 1 mag and alternative attenuation 0 mag. Their
relative gain reaches the upper permitted bound. The independent-amplitude
case selects model009 versus model012, both at 1 mag, with relative N III gain
8.53866. Its information fraction is 4.90444e-8: small but finite resolved
component-shape differences survive. This limit does not prove exact physical
nonidentifiability. Ten paired-environment controls are also retained; their
hardest-case SNR changes from 10.6771 to 11.4024 under ±50%, and to 9,001.3
under independent ion amplitudes.

All SNRs are enhanced truth's matched total bundle SNR for expected squared
separation 9, under white wavelength noise and known centroid, continuum and
nominal Gaussian LSF. That distance is not a calibrated significance or
model-selection probability. No source-specific instrument sensitivity,
aperture/detector coverage, exposure time, component noise transport or
relative ion response has been measured. Both gas compositions retain custom
C/N/O abundances and the original finite family; unmodeled physical families
can change these results. The test does not alter RATE-v3 uncertainty.

## Reproduction and checks

The [artifact](../research_output/mom_cloudy_ion_gain.json) records every
hardest pair, matched-environment controls, exact model/plan hashes and budget
accounting. Computation took about 1.8 seconds against a 120-second cap;
new transfer was zero bytes. The fixed pilot stops here. Its next useful
step is physical validation of whether the N III/C III ratio and the
source-specific response can be bounded, not more nuisance-grid expansion.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BLIS_NUM_THREADS=1
python -m tools.jwst.cloudy_ion_gain \
  --output /tmp/mom-cloudy-ion-gain.json
python -m pytest tests/test_cloudy_ion_gain.py tests/test_cloudy_observation_contrasts.py -q
```

Sixteen focused tests pass. Synthetic controls verify that free ion amplitudes
erase a pure inter-ion scaling difference while preserving component-shape
differences. Forty-eight seeded positive-Gram cases compare the analytic cone
solution with independent whitened SciPy NNLS. The no-gain finite-model case
reproduces the reviewed forecast, and nested gain envelopes decrease its
information monotonically. Numerical-zero cases encode null required SNR
with an explicit nonidentifiable status; no JSON infinity is used.

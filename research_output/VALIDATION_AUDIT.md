# Validation audit of committed injection outcomes

Input SHA-256: `5409d2dfea19e0d3617440396f779f7ca89f6c431577b73f008812af1e7ef017`

Every rate below is recomputed from per-source outcomes. Brackets are
95% Wilson binomial intervals conditional on these trials, not total scientific uncertainty.

| Filter/sample | Detected / injected | Rejected / classified | Accepted / injected |
| --- | --- | --- | --- |
| F277W overall | 1069/1600 = 66.8% [64.5, 69.1]% | 5/1069 = 0.5% [0.2, 1.1]% | 1064/1600 = 66.5% [64.2, 68.8]% |
| F277W faint_point_sources | 85/134 = 63.4% [55.0, 71.1]% | 0/85 = 0.0% [0.0, 4.3]% | 85/134 = 63.4% [55.0, 71.1]% |
| F356W overall | 1028/1599 = 64.3% [61.9, 66.6]% | 1/1028 = 0.1% [0.0, 0.5]% | 1027/1599 = 64.2% [61.8, 66.5]% |
| F356W faint_point_sources | 61/135 = 45.2% [37.0, 53.6]% | 0/61 = 0.0% [0.0, 5.9]% | 61/135 = 45.2% [37.0, 53.6]% |
| F444W overall | 851/1600 = 53.2% [50.7, 55.6]% | 12/851 = 1.4% [0.8, 2.4]% | 839/1600 = 52.4% [50.0, 54.9]% |
| F444W faint_point_sources | 27/119 = 22.7% [16.1, 31.0]% | 0/27 = 0.0% [0.0, 12.5]% | 27/119 = 22.7% [16.1, 31.0]% |

An observed zero rejection rate has a nonzero upper uncertainty bound.
Passing the classifier is conditional on detection; it does not restore sources missed by the detector.
Null classifier decisions remain unknown, never accepted by default.

## Limits

- These are committed synthetic injection trials, not independent real-source recovery.
- Legacy trials do not record stable source, field, visit, generator and PSF provenance.
- Wilson intervals assume independent Bernoulli trials. Shared images/PSFs and batch clustering may narrow them artificially.
- No detector calibration, PSF mismatch or astrophysical systematics are included.
- No new FITS processing or source observations were performed.

# Stage-2b Artifact Characterization

Two independent exposures of the same sky in the same filter form a
labelled truth set. Nothing astrophysical at cosmological distance varies
over a few hours, so a source detected in one exposure and absent from the
other is a detector event that survived Stage-2b calibration.

Measured with `python discovery/artifact_characterization.py --auto`.

## Per-pair results

### F277W

- Epochs: `jw01180025001_13201_00002_nrcalong_i2d` x `jw01180026001_07201_00001_nrcalong_i2d`
- Time baseline: 5.65 h
- Exposure time: 944.8 s
- Shared sky area: 2.465 arcmin^2
- Sources compared (both directions): **1256**
- Persistent: **1066**
- Single-epoch (artifacts): **190** (15.1%)
- Surviving-artifact density: **38.5 per arcmin^2 per exposure**
- Normalized: 40.8 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.993 +/- 0.078**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 79 | 16 | 20.3% |
| 8-12 | 208 | 22 | 10.6% |
| 12-20 | 301 | 36 | 12.0% |
| 20-50 | 430 | 66 | 15.3% |
| >50 | 238 | 50 | 21.0% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 15.7%, 14.5%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 38.5 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1285 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 2.994 | 1.324 |
| ellipticity | 0.370 | 0.297 |
| area (px) | 23.000 | 7.000 |
| peak/total flux | 0.092 | 0.395 |

### F356W

- Epochs: `jw01180025001_05201_00003_nrcalong_i2d` x `jw01180026001_05201_00003_nrcalong_i2d`
- Time baseline: 9.55 h
- Exposure time: 944.8 s
- Shared sky area: 2.415 arcmin^2
- Sources compared (both directions): **981**
- Persistent: **828**
- Single-epoch (artifacts): **153** (15.6%)
- Surviving-artifact density: **31.7 per arcmin^2 per exposure**
- Normalized: 33.5 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.991 +/- 0.079**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 48 | 12 | 25.0% |
| 8-12 | 121 | 18 | 14.9% |
| 12-20 | 226 | 18 | 8.0% |
| 20-50 | 371 | 65 | 17.5% |
| >50 | 215 | 40 | 18.6% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 15.0%, 16.0%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 31.7 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1056 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.119 | 1.383 |
| ellipticity | 0.349 | 0.266 |
| area (px) | 25.000 | 7.000 |
| peak/total flux | 0.081 | 0.335 |

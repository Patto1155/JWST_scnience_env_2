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
- Persistent: **1074** (of which 8 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **182** (14.5%)
- Surviving-artifact density: **36.9 per arcmin^2 per exposure**
- Normalized: 39.1 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.993 +/- 0.079**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 79 | 15 | 19.0% |
| 8-12 | 208 | 21 | 10.1% |
| 12-20 | 301 | 34 | 11.3% |
| 20-50 | 430 | 63 | 14.7% |
| >50 | 238 | 49 | 20.6% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 15.3%, 13.7%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 36.9 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1231 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 2.989 | 1.310 |
| ellipticity | 0.370 | 0.293 |
| area (px) | 23.000 | 6.000 |
| peak/total flux | 0.092 | 0.404 |

### F356W

- Epochs: `jw01180025001_05201_00003_nrcalong_i2d` x `jw01180026001_05201_00001_nrcalong_i2d`
- Time baseline: 8.92 h
- Exposure time: 944.8 s
- Shared sky area: 2.415 arcmin^2
- Sources compared (both directions): **982**
- Persistent: **832** (of which 9 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **150** (15.3%)
- Surviving-artifact density: **31.1 per arcmin^2 per exposure**
- Normalized: 32.9 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.992 +/- 0.086**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 43 | 12 | 27.9% |
| 8-12 | 133 | 18 | 13.5% |
| 12-20 | 223 | 22 | 9.9% |
| 20-50 | 376 | 65 | 17.3% |
| >50 | 207 | 33 | 15.9% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 15.0%, 15.5%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 31.1 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1035 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.084 | 1.334 |
| ellipticity | 0.356 | 0.282 |
| area (px) | 25.000 | 7.000 |
| peak/total flux | 0.082 | 0.365 |

### F356W

- Epochs: `jw01180025001_05201_00003_nrcalong_i2d` x `jw01180026001_05201_00002_nrcalong_i2d`
- Time baseline: 9.23 h
- Exposure time: 944.8 s
- Shared sky area: 2.415 arcmin^2
- Sources compared (both directions): **963**
- Persistent: **815** (of which 9 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **148** (15.4%)
- Surviving-artifact density: **30.6 per arcmin^2 per exposure**
- Normalized: 32.4 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.991 +/- 0.085**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 41 | 10 | 24.4% |
| 8-12 | 123 | 19 | 15.4% |
| 12-20 | 218 | 20 | 9.2% |
| 20-50 | 364 | 54 | 14.8% |
| >50 | 217 | 45 | 20.7% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 14.8%, 15.7%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 30.6 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1022 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.151 | 1.347 |
| ellipticity | 0.357 | 0.255 |
| area (px) | 25.000 | 7.000 |
| peak/total flux | 0.082 | 0.359 |

### F356W

- Epochs: `jw01180025001_05201_00003_nrcalong_i2d` x `jw01180026001_05201_00003_nrcalong_i2d`
- Time baseline: 9.55 h
- Exposure time: 944.8 s
- Shared sky area: 2.415 arcmin^2
- Sources compared (both directions): **981**
- Persistent: **832** (of which 4 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **149** (15.2%)
- Surviving-artifact density: **30.9 per arcmin^2 per exposure**
- Normalized: 32.7 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.990 +/- 0.079**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 48 | 11 | 22.9% |
| 8-12 | 121 | 17 | 14.0% |
| 12-20 | 226 | 18 | 8.0% |
| 20-50 | 371 | 63 | 17.0% |
| >50 | 215 | 40 | 18.6% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 15.0%, 15.3%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 30.9 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1028 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.115 | 1.374 |
| ellipticity | 0.348 | 0.266 |
| area (px) | 25.000 | 7.000 |
| peak/total flux | 0.082 | 0.344 |

### F356W

- Epochs: `jw01180026001_05201_00001_nrcalong_i2d` x `jw01180026001_05201_00002_nrcalong_i2d`
- Time baseline: 0.31 h
- Exposure time: 944.8 s
- Shared sky area: 4.484 arcmin^2
- Sources compared (both directions): **2295**
- Persistent: **1965** (of which 21 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **330** (14.4%)
- Surviving-artifact density: **36.8 per arcmin^2 per exposure**
- Normalized: 38.9 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.997 +/- 0.081**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 149 | 40 | 26.8% |
| 8-12 | 384 | 38 | 9.9% |
| 12-20 | 554 | 55 | 9.9% |
| 20-50 | 749 | 126 | 16.8% |
| >50 | 459 | 71 | 15.5% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 13.7%, 15.0%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 36.8 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1227 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.073 | 1.305 |
| ellipticity | 0.351 | 0.285 |
| area (px) | 23.000 | 6.000 |
| peak/total flux | 0.085 | 0.388 |

### F356W

- Epochs: `jw01180026001_05201_00001_nrcalong_i2d` x `jw01180026001_05201_00003_nrcalong_i2d`
- Time baseline: 0.63 h
- Exposure time: 944.8 s
- Shared sky area: 4.484 arcmin^2
- Sources compared (both directions): **2302**
- Persistent: **1975** (of which 16 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **327** (14.2%)
- Surviving-artifact density: **36.5 per arcmin^2 per exposure**
- Normalized: 38.6 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.995 +/- 0.082**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 142 | 34 | 23.9% |
| 8-12 | 377 | 30 | 8.0% |
| 12-20 | 560 | 53 | 9.5% |
| 20-50 | 763 | 137 | 18.0% |
| >50 | 460 | 73 | 15.9% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 13.7%, 14.7%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 36.5 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1215 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.041 | 1.313 |
| ellipticity | 0.347 | 0.272 |
| area (px) | 23.000 | 7.000 |
| peak/total flux | 0.085 | 0.370 |

### F356W

- Epochs: `jw01180026001_05201_00002_nrcalong_i2d` x `jw01180026001_05201_00003_nrcalong_i2d`
- Time baseline: 0.32 h
- Exposure time: 944.8 s
- Shared sky area: 4.484 arcmin^2
- Sources compared (both directions): **2316**
- Persistent: **1979** (of which 13 recovered by the wide-annulus recheck)
- Single-epoch (artifacts): **337** (14.6%)
- Surviving-artifact density: **37.6 per arcmin^2 per exposure**
- Normalized: 39.8 per arcmin^2 per kilosecond

Method validation - persistent sources have a cross-epoch flux ratio of **0.997 +/- 0.077**. A value at 1 confirms the cross-epoch photometry is sound, so the single-epoch population is a real absence rather than a measurement failure.

| SNR range | sources | single-epoch | artifact fraction |
| --- | ---: | ---: | ---: |
| 5-8 | 146 | 33 | 22.6% |
| 8-12 | 374 | 39 | 10.4% |
| 12-20 | 563 | 48 | 8.5% |
| 20-50 | 756 | 126 | 16.7% |
| >50 | 477 | 91 | 19.1% |

Direction symmetry - searching each exposure in turn gives single-epoch fractions of 14.6%, 14.5%. A stochastic per-exposure process must look the same whichever exposure is searched, and it does.

Contamination of a dropout search: an artifact appears in exactly one exposure, so it is absent from every other band by construction and passes any dropout cut with full efficiency. At 37.6 artifacts per arcmin^2 against an assumed 0.030 genuine z > 10 sources per arcmin^2, that is **~1253 artifacts per real high-redshift source**.

| morphology (median) | persistent | single-epoch |
| --- | ---: | ---: |
| FWHM (px) | 3.057 | 1.329 |
| ellipticity | 0.347 | 0.276 |
| area (px) | 23.000 | 7.000 |
| peak/total flux | 0.085 | 0.372 |

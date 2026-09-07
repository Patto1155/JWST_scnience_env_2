# Injection-Recovery: what the artifact cut costs

Synthetic sources spanning brightness, size and surface brightness were
injected into real JWST exposures and put through the complete detection,
morphology and classification chain. Because the truth is known, this
measures directly what a ROC AUC cannot: how many real galaxies the
artifact cut deletes, and which ones.

`false rejection` is the fraction of **detected, genuinely real** injected
sources that the classifier flags as artifacts at threshold 0.5.

## F277W

- Injected: **1600**
- Detected: **1069** (66.8%)
- Falsely rejected by the classifier: **144** (13.5% of detected)

| injected S/N | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 5 | 7% | 63.2% | 3% |
| 8 | 55% | 57.1% | 24% |
| 12 | 86% | 15.6% | 73% |
| 20 | 90% | 2.0% | 89% |
| 40 | 83% | 0.0% | 83% |
| 100 | 79% | 1.4% | 78% |

| half-light radius (px) | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 0.00 | 79% | 33.7% | 52% |
| 0.75 | 75% | 11.1% | 67% |
| 1.50 | 59% | 0.4% | 59% |
| 3.00 | 54% | 0.5% | 54% |

Calibration check - injected target versus median measured aperture S/N:

| target S/N | median measured S/N | n |
| ---: | ---: | ---: |
| 5 | 3.6 | 19 |
| 8 | 7.2 | 154 |
| 12 | 10.9 | 231 |
| 20 | 18.8 | 244 |
| 40 | 37.4 | 211 |
| 100 | 91.8 | 210 |

| population | detected | false rejection |
| --- | ---: | ---: |
| isolated | 73% | 14.4% |
| within 8-20 px of a bright source | 53% | 10.6% |
| **unresolved and faint (S/N <= 8, r_e = 0)** | 63% | 80.0% |

## F356W

- Injected: **1599**
- Detected: **1028** (64.3%)
- Falsely rejected by the classifier: **1** (0.1% of detected)

| injected S/N | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 5 | 51% | 0.8% | 50% |
| 8 | 56% | 0.0% | 56% |
| 12 | 63% | 0.0% | 63% |
| 20 | 64% | 0.0% | 64% |
| 40 | 72% | 0.0% | 72% |
| 100 | 81% | 0.0% | 81% |

| half-light radius (px) | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 0.00 | 61% | 0.0% | 61% |
| 0.75 | 64% | 0.4% | 64% |
| 1.50 | 63% | 0.0% | 63% |
| 3.00 | 69% | 0.0% | 69% |

Calibration check - injected target versus median measured aperture S/N:

| target S/N | median measured S/N | n |
| ---: | ---: | ---: |
| 5 | 5.0 | 129 |
| 8 | 7.3 | 153 |
| 12 | 11.1 | 182 |
| 20 | 18.2 | 175 |
| 40 | 36.3 | 173 |
| 100 | 76.9 | 216 |

| population | detected | false rejection |
| --- | ---: | ---: |
| isolated | 77% | 0.0% |
| within 8-20 px of a bright source | 35% | 0.6% |
| **unresolved and faint (S/N <= 8, r_e = 0)** | 45% | 0.0% |

## F444W

- Injected: **1600**
- Detected: **851** (53.2%)
- Falsely rejected by the classifier: **245** (28.8% of detected)

| injected S/N | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 5 | 2% | 60.0% | 1% |
| 8 | 16% | 79.1% | 3% |
| 12 | 70% | 52.1% | 34% |
| 20 | 85% | 23.8% | 65% |
| 40 | 77% | 26.5% | 57% |
| 100 | 68% | 0.5% | 68% |

| half-light radius (px) | detected | false rejection | net completeness |
| ---: | ---: | ---: | ---: |
| 0.00 | 61% | 77.2% | 14% |
| 0.75 | 61% | 23.5% | 47% |
| 1.50 | 49% | 1.0% | 48% |
| 3.00 | 41% | 0.0% | 41% |

Calibration check - injected target versus median measured aperture S/N:

| target S/N | median measured S/N | n |
| ---: | ---: | ---: |
| 5 | 6.7 | 5 |
| 8 | 7.2 | 43 |
| 12 | 10.9 | 194 |
| 20 | 18.7 | 227 |
| 40 | 37.2 | 196 |
| 100 | 90.6 | 186 |

| population | detected | false rejection |
| --- | ---: | ---: |
| isolated | 61% | 26.6% |
| within 8-20 px of a bright source | 36% | 37.4% |
| **unresolved and faint (S/N <= 8, r_e = 0)** | 23% | 88.9% |

# Independent CHIME/FRB feasibility review

This is an independent review of the bounded Catalog 2 pilot, not evidence for
a new FRB mechanism. GOODS-N outcomes remain unopened. The author owns the
single catalog acquisition; this reviewer downloaded no catalog or spectra.

## Accessibility checked on 12 October 2026

Direct HTTP requests found the [CHIME public portal](https://chime-frb.ca/catalog2)
temporarily serving an infrastructure-rebuild page (HTTP 200, 7,355 body bytes).
It links the permanent Catalog 2 archive:

https://www.canfar.net/storage/list/AstroDataCitationDOI/CISTI.CANFAR/25.0066/data

The [DOI landing page](https://doi.org/10.11570/25.0066) returned HTTP 200
and 19,432 bytes. The official GitHub organization metadata returned 25,419
bytes. These three direct metadata transfers total 52,206 bytes. Search-service
retrieval bandwidth is not included. No login or paid service was used.

## Measurement contract

The [Catalog 2 paper](https://arxiv.org/html/2601.09399v1), section III.3 and
Table 4, identifies DM and scattering as global parameters shared by sub-bursts
within an event. They are jointly fit to the same dynamic spectrum. Scattering
is tabulated in seconds at 400.1953125 MHz; the fixed frequency exponent is
-4. An F-test chooses between zero-scattering and freely fitted scattering
models. The tabular schema provides scalar errors rather than a DM/scattering
cross covariance. Thus sub-burst rows cannot be counted as independent DM/tau
measurements, and excluded or zero-model rows cannot be interpreted as measured
zero scattering.

[Curtin et al.](https://arxiv.org/html/2411.02870v2), section I, discusses
the inability to separate downward frequency drift from small dispersion delays
or scattering at millisecond resolution. Higher time resolution is needed to
identify structure-aligned DM robustly. A catalog-only covariance therefore
cannot by itself identify local plasma changes.

## Independent design judgment

The narrow quality screen is acceptable for a conditional feasibility pilot.
Its detection threshold, single-component restriction, broad-band restriction
and resolution cut may strongly limit the retained repeater sample. The frozen
minimum is six sources with at least six qualifying events each, split into
an earlier floor(n/2) half and the remaining later half, at least three in each.
Failing that gate ends the declared covariance experiment.

Within-source covariance uses centered DM and log(reference-frequency tau),
with n-1 normalization, followed by equal weighting across qualifying sources.
Peak-frequency-transformed scattering is used only for the resolution cut.
Normalized correlations are secondary diagnostics. No calibrated p-value is
implied by the internal chronological split.

The mean sigma_DM sigma_tau/tau calculation bounds expected random-error
cross covariance only under independent, unbiased event errors and a first-order
log transformation. It does not bound morphology/model bias or temporally
correlated systematic errors. Multiplying that quantity by 25 after fivefold
error inflation is a sensitivity scenario, not a calibrated systematic bound.

## Executed independent gate

The exact public CSV is 4,057,396 decompressed bytes, SHA256
`5108ada779d279a2547d9f9e73ae25bfdd40d8496d6ba7255ec29c6629057a48`.
The durable input is `data_sources/research4/chimefrbcat2.csv.gz`; the receipt
pins its compressed artifact hash separately from the source CSV identity.
The independent implementation is `discovery/research4_frb_review.py`; it imports
no author analysis. The receipt is `research_output/research4_frb_review.json`.
All 29 selected event identities, source counts, input hash and stopping decision
match the author receipt exactly. Intermediate rejection attributions use a
different grouping/order, so they should not be mistaken for additional data.

| Independent sequential screen | Remaining events |
|---|---:|
| Unique event IDs from 5,045 rows | 4,539 |
| Nonempty repeater label | 981 |
| Four nominal-operation/model flags zero | 876 |
| Single catalog component | 715 |
| Fitted SNR at least 20 | 347 |
| Finite DM, positive tau and positive scalar errors | 139 |
| Scattering/error at least 5 | 137 |
| Bandwidth at least 200 MHz | 33 |
| Peak-frequency scattering resolved by two samples | 29 |
| Finite infinite-frequency MJD | 29 |

Shared DM, scattering and source-label values are consistent across each
event's sub-burst rows. The retained sample has 19 source labels and at most
four qualifying events per source. **Zero sources pass the six-event gate;
the frozen covariance pilot stops. No outcome covariance was computed.**
These conditional counts do not estimate astrophysical source prevalence or
the incidence of dynamic plasma. Relaxing observed cuts cannot rescue the
frozen design. Higher-resolution remeasurement or a separate fresh design
would be required before pursuing the physical mechanism claim.

Four focused tests passed, checking exact n-1 covariance on synthetic six-source
controls, stopping at five sources, and exclusion of limit-valued scattering
and repeated sub-burst rows, plus gzip identity/selection invariance. Lint,
formatting and configured type checking with
explicit package bases pass for the oracle and these tests. These synthetic
controls validate software behavior, not actual FRB physics.

Reproduce with the exact research lock and one BLAS thread:

```bash
python -m discovery.research4_frb_review \
  --catalog data_sources/research4/chimefrbcat2.csv.gz \
  --output /tmp/research4-frb-review.json \
  --author-results research_output/research4_frb_results.json \
  --freeze docs/RESEARCH4_FRB_FREEZE.md
```

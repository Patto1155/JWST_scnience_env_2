# CHIME temporal plasma pilot freeze, 12 October 2026

Frozen before downloading/opening catalog outcomes. Exploratory feasibility and
conditional association pilot, not a confirmatory discovery claim. Parent
authorized <=100 MB free acquisition and <=5 minutes per numerical run.

Question: across repeating FRB sources, do fitted dispersion measure (DM) and
log scattering time co-vary within source, consistently in chronological halves?
Positive co-variation is one prediction of changing electron columns and
turbulence along a common line of sight. It does not uniquely imply evolving
circumsource plasma: source motion, intervening plasma, intrinsic frequency
drift, and shared fit biases remain alternatives.

Use CHIME/FRB Catalog 2, DOI https://doi.org/10.11570/25.0066,
public CSV listed at
https://www.canfar.net/storage/list/AstroDataCitationDOI/CISTI.CANFAR/25.0066/data/table.
Primary methods https://arxiv.org/html/2601.09399v1, especially section III.3
and Appendix A; prior morphology https://arxiv.org/html/2411.02870v2.
Cook et al. https://arxiv.org/abs/2605.08410 already reports four secular DM
changes; their existence is not novelty here. Curtin et al. already examined
individual DM/scattering slopes and across-source DM/scattering correlation.
A broader within-source covariance with controlled temporal replication is
only potentially new, not novelty established by search silence.

## Frozen selection

1. Group by event_id; verify each event's DM and scattering values are global
   duplicates across sub-bursts. Keep lowest sub_num. Treat events, not
   sub-bursts, as sampling units. Require exactly one catalog row per event
   for the primary screen, reducing intrinsic drifting multi-component ambiguity.
2. A nonempty repeater_name; excluded_flag, sidelobe_flag, intrachan_flag,
   catalog1_param_flag all zero. snr_fitb >=20.
3. Finite DM, DM error, scattering, scattering error, peak/low/high frequencies,
   and mjd_inf. Both errors positive, scattering positive, tau/error >=5.
4. high_freq-low_freq >=200 MHz. Require scattering at peak frequency >=
   2*0.000983 s, using catalog reference 400.1953125 MHz and fixed exponent -4.
   This transformed quantity is used for selection only; primary response is
   log(reference-frequency scattering), not log(scattering at a changing peak).
5. At least six sources have >=6 qualifying events each. Sort each source by
   mjd_inf then event_id. Earlier floor(n/2) events are discovery half; later
   events are test half, thus at least three each. Membership is based on the
   frozen quality cuts; no source association/outcome is used to split/select.

If coverage fails, stop before computing outcome associations. Do not relax
cuts on observed values. Report the entire screening flow and rejection reason.
Zero scattering denotes a selected no-scattering model, not physical zero or a
numerical upper limit. Excluding it restricts inference to detected-scattering
events and cannot estimate the incidence of changing plasma in the population.

## Frozen statistic and interpretation

If coverage passes, each source's primary value is the centered sample
covariance (ddof=1) of DM and natural-log reference tau; average equally over
sources. Report individual values, half covariances, normalized correlations,
and leave-one-source-out means to expose source leverage. No catalog-only
calibrated p-value or astrophysical detection is authorized by this pilot.

For each source report mean(sigma_DM*sigma_tau/tau) as a Cauchy-Schwarz upper
bound on the expected contribution of arbitrary same-event *random* fit-error
covariance, conditional on independent unbiased event errors and a first-order
log approximation. Also report 25 times that bound (both errors inflated five
times) as an explicitly uncalibrated sensitivity. Neither bounds morphology
mis-modeling, systematic bias, cross-event correlation, or uncertainty in the
fixed frequency exponent. Temporal sign agreement alone does not remove these.

Strong candidates require new dynamic-spectrum remeasurement with free
scattering index, structure-based DM and joint-error modeling before a physical
claim. Do not fit more nuisance grids merely to generate headline significance.

## Independent review

The baseline agent reviewed the schema and freeze before acquisition and
endorsed this narrow conditional contract, including its stopping gate and
limits. An independent reader must reproduce event counts and selection from
the same hash-pinned catalog rather than trusting the author's filtered rows.

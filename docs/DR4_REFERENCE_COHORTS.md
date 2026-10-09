# Real reference cohorts, not recovery measurements

This round builds on the checksummed public-source pilot. Run:

```bash
python -m data_pipeline.reference_cohorts data_sources/pilot/jades_dr4_reference.csv --output /tmp/dr4-cohorts.json
```

The output deterministically reproduces `data_sources/pilot/jades_dr4_cohorts.json`
and checks the input against its acquisition receipt before reading labels.

| Field | Observation rows | Highly robust A/B | A/B z≥6 | A/B 0≤z<3 |
|---|---:|---:|---:|---:|
| GOODS-N | 1,803 | 1,063 | 80 | 584 |
| GOODS-S | 3,387 | 1,795 | 163 | 877 |
| Total | 5,190 | 2,858 | 243 | 1,461 |

Every row has finite valid sky coordinates. The release has 5,190 distinct
`(TIER, NIRSpec_ID)` keys and Unique_ID values, but neither count is the number of
unique astrophysical sources. The same object can have different target IDs and
repeat observations across tiers. NIRSpec_ID alone is not a deduplication key.

Quality is retained: A=2,651; B=207; C=439; D=493; E=1,400. There are 1,393
nonfinite or negative redshift values; quality E need not match that number because
some entries contain placeholder or other redshift information. **Use quality and
redshift jointly**, never only a numeric redshift threshold.

The A/B high-z cohort spans z≈6.000–10.603. A separate C high-z cohort contains
48 secure-break/weak-line observations, up to z=14.1796. It includes repeated
observations of the z≈12.48 and z≈13.2 targets. Excluding C to obtain a clean strong
emission-line reference removes some of the earliest galaxies. That exclusion
must be visible when measuring pipeline recovery; these are not failed detections.

The low-z cohort consists of spectroscopic control references. Those galaxies have
**not** been demonstrated to masquerade as high-z dropouts. Recovering them in an
image is a different experiment. Neither cohort estimates contamination prevalence
or total selection completeness because the spectra were selectively targeted.

Original candidate catalogues contain saved RA/Dec values derived from WCS, but
the original FITS WCS/frame has not been independently verified in this round.
Consequently the report deliberately records `candidate_crossmatch:not_performed`.
A later experiment must validate that frame, image footprints and coverage, match
using spherical coordinates, track ambiguous neighbours and group repeated
observations before making recovery claims.

## MoM-z14 is a separate field and separate pilot

JADES DR4 covers GOODS-N/S; MoM-z14 is in COSMOS. The released GOODS reference
catalogue cannot supply its spectrum. The source pilot now separately contains an
actual public DAWN processed MoM-z14 spectrum, not merely a transcribed paper table.

The published coordinate query returns `mom-cos04-v4`, source ID 277193 in program
5224. The downloaded FITS SLITS coordinates and ID exactly agree within 1e-6 deg.
`data_sources/pilot/mom_z14_identity.json` records that identity check and the SHA256
of both the spectrum and the archived spatial-query response. The 473-bin SPEC1D
has explicit µm wavelengths and µJy flux/error/sky units; the 2D products and
individual-exposure metadata are also retained. Bytes are pinned by an acquisition
receipt and product entry in the source manifest.

The public index redshift 14.480445 and published v2 UV-line redshift 14.44 are
**different fitting outputs**. No new redshift, line significance, chemical abundance
or maturity estimate is inferred by this acquisition. The spatial query also finds
a CAPERS extraction with an untrusted grade-1 low-redshift fit at the same source
position; that does not establish a competing redshift. Inspect extraction and
fitting choices if reconciling such automated catalogue values.

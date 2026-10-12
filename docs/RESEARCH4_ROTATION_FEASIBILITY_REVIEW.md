# Independent rotation-pair feasibility review

This round assessed a possible conditional empirical pattern: whether mass-order
rotation reversals concentrate near an intermediate-period transition and persist
in a separately observed survey. **No new rotation pattern was measured.**
GOODS-N outcomes remain unopened. The coordinator allowed a fresh 160,000,000
response-body-byte budget and ten minutes numerical runtime; the large TARS
catalog was not acquired because the proposed novel empirical endpoint remained
undefined, not because of the earlier 100 MB limit.

## Actual small-table accessibility and metadata

The [Gruner et al. (2023) CDS release](https://cdsarc.cds.unistra.fr/ftp/J/A+A/675/A180/)
supplies `ReadMe` and `tablec1.dat`. Both returned HTTP 200. The latter is 249,984
bytes, SHA256 `9be15c613e7e34459eff0057972bed1b2c0c12daf6bc376879eac949bcd8fe94`.
The ReadMe is 7,681 bytes, SHA256
`dfefce41b8a4a80962e11b3e213ca8cceec50668d18c8c7c97ed7953fe4b9a73`.
The two files are retained under `data_sources/research4/rotation_pairs/` and the
receipt is `research_output/research4_rotation_metadata_review.json`.

Only binary identifiers, exact Gaia DR3 identifier strings, astrometry and
photometry were parsed. Rotation periods, errors, rotation classifications and
rotational age groups were not accessed. Each of the 372 binary identifiers has
exactly two component rows. Metadata counts are:

| Metadata condition | Pairs |
|---|---:|
| All binary identifiers | 372 |
| Both parallaxes greater than 2 mas | 287 |
| Both parallaxes greater than 2 mas and both Gaia G less than 16 | 207 |

Gaia G is not TESS magnitude. These are rough input feasibility counts, not an
executed TARS crossmatch or guaranteed dual-period detections. Direct acquisition
totaled 265,346 bytes: table 249,984 plus two ReadMe fetches of 7,681 each. Web
search-service bandwidth is not measured. No light curves or sector catalogs
were acquired.

## Independent scientific judgment

A conditional empirical relation with independent survey validation is a valid
research objective; it need not identify a unique physical cause. The available
identifiers and nearby stars make a small external validation plausible in
principle. However, the candidate must add a distinct observation or prediction
beyond a previously reported relation.

The [primary Gruner paper](https://arxiv.org/html/2307.10836v1), sections I,
4.1 and 4.3.1, already discusses redder stars rotating faster, pairs following
peaks and troughs of nonmonotonic rotation-color sequences, and an emerging
sinusoidal sequence with age. A new TESS count in a chosen period band could
quantify external replication of these relations, but that does not yet define
a novel empirical result for this campaign.

There are concrete selection and validation limits. The Gruner table is already
selected through Kepler/K2 rotation detection and vetting. Its `Class` and
`Agegroup` columns encode rotation-derived judgments and cannot serve as blind
metadata cuts. The TARS adopted-period table is detection-conditioned. Repeating
its classifier or sector measurements does not restore a nondetection denominator.
These limits prevent a population/causal interpretation, while still allowing
a carefully labeled conditional validation. Low TESS spatial resolution also
requires source-attribution and companion-contamination controls before treating
two listed periods as independently measured stellar rotations.

The reviewer therefore supports **stopping this proposed acquisition pending a
specific distinct empirical endpoint and primary-literature comparison**. This
is not evidence against a rotation transition, a claim that no novel use of TARS
exists, or a finding from the unacquired catalog. A future design could proceed
with fixed predictions, independent source attribution and meaningful paired
overlap; it must document whether it extends or merely replicates the known
mass-ordering relation.

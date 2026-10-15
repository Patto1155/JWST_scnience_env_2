# Bounded other-arm assessment, 15 October 2026

G235H remains paused because current metadata access is blocked; this does not
establish that public G235H exposures are absent. The SMACS empirical-PSF attempt
closes with unmet identity, saturation and held-out calibration prerequisites.
No science data were acquired, no new outcome arrays opened and no state files
edited. Root owns the raw-known-answer response and MoM S/N-law extrapolation
once the diagnostic verdict and fitted laws are available.

## Freeze, access and resources

The metadata-only plan was committed as `603e91154b862d13b0480748c312133964caac22`
before the sole MAST attempt at 2026-10-15T04:58:48.774362 UTC. The ordinary
inherited proxy returned `Tunnel connection failed: 403 Forbidden`; no MAST
response body reached the client. There was no retry or bypass. The environment
status tool reported current observations, restricted policy and policy state
`unknown`; the local v1 policy lists no MAST/STScI astronomy destination and no
VPN. We do not equate desired policy with demonstrated enforcement: the actual
CONNECT failure is the observed access result.

Receipt: [e_metadata_receipt.json](../research_output/flux_deficit_20261015/e_metadata_receipt.json).
The retained [response body](../research_output/flux_deficit_20261015/e_mast_metadata.response)
is empty; its SHA256 is recorded. HTTP CONNECT status is carried in the exception,
not misrepresented as an archive HTTP response. Received metadata body bytes:
**0 / 10,000,000**; science bytes **0 / 1,073,741,824**. These are application
response-body counts, not network-protocol overhead. Free disk was
30,888,218,624 bytes before and after the query, above the 5 GB floor. Existing
SMACS compact hash reads total 1,658,880 local bytes and incur no transfer charge.
Historical arms' budgets are neither reset nor reassigned by this receipt.

## MoM metadata and programme leads

Target is (150.0933255, 2.2731627 degrees), z=14.44. The existing
[public inventory](MOM_PUBLIC_METADATA_AUDIT.md), with compact evidence in
[mom_public_metadata_v1.json](../research_output/mom_public_metadata_v1.json),
contains these leads; none establishes public on-source G235H NIII/CIII coverage:

| Program | Existing evidence and limitation |
| --- | --- |
| 5224 | MoM PRISM/CLEAR, source277193, executed PUBLIC source-level observation `jw05224-o004_s000277193_nirspec_clear-prism`, obsid254258482. |
| 6368 | CAPERS PRISM/CLEAR, source102896, 0.03058 arcsec away, 18 disjoint roots; executed PUBLIC `jw06368-o007_s000102896_nirspec_clear-prism`, obsid266381037. Released range3.938–5.502 µm misses the target UV bundles. |
| 6434, 5893 | Executed NIRCam grism footprints, not extracted target NIRSpec G235H spectra. |
| 10361, 11892 | Historical position-query entries have null observation times; PUBLIC does not establish execution. |

The historical cone inventory is fully paginated (35 records); product/program
inventories are partial. Its older snapshot plus today's blocked query cannot
establish current completeness or absence. These IDs are inventory leads, not
verified G235H programme assignments. Follow the existing
[G235H next design](frozen/D_G235H_NEXT_DESIGN.md): executed/public identity,
source shutter, native usable coverage of both multiplets and exact accession
must precede science download. No substitute grating or target was selected.

## MoM existing fluxes and the S/N premise

[e_mom_existing_comparison.json](../research_output/flux_deficit_20261015/e_mom_existing_comparison.json)
transcribes the existing published table and fresh conditional fit only. Ratios
are 0.471, 0.517, 0.401, 0.247 and 0.613 for NIV, CIV, HeII+OIII, NIII and
CIII. Their fresh fit/error S/N values are2.09,2.18,1.52,0.81,1.98; the published
reported S/N values are3.4,3.4,3.0,2.7,2.8. **A's predictor uses published
flux/error**, so the fresh S/N≈1–3 premise must not supply its covariate.
Average asymmetric published errors give S/N3.437,3.438,2.980,2.681,2.810.
All remain outside A's training S/N5–30. Published intervals are asymmetric;
averaging errors is an explicitly descriptive sensitivity convention. The
published NIV1487 label and fresh total-doublet contract also differ. An
extrapolated curve cannot certify published consistency or justify a correction
without accounting for scatter, shared photons and different operators/LSFs.

## SMACS empirical PSF

The retained same-frame inputs are the two compact F444W products from program
2736, visit `jw02736001001`, exposure endings00003 and00004. Both hash exactly
match the prior receipt; the
[prerequisite inventory](../research_output/flux_deficit_20261015/e_psf_prerequisites.json)
records their identities and the two relevant local compact FITS paths. No
SCI arrays were interpreted or fit in this assessment; bytes were read only to
verify hashes.

The prior [completion report](SMACS1043_COMPLETION.md) and
[d_verification.json](../research_output/calibrated_20261014/d_verification.json)
establish that compact extensions are SCI/ERR/WHT, omitting native DQ. The
metadata-selected isolated core1030 is not independently identified as a star;
its unsaturation is unverified and there is no independent held-out measured-PSF
reduced-chi2≤2 control. Absence of DQ does not show saturation; it prevents this
retained product from certifying unsaturation. A core fit to itself, an imported
PSF or a synthetic Gaussian does not meet the frozen prerequisite.

Thus no supported same/close-frame unsaturated stellar sample is available in
the retained inputs. Access restrictions prevent the required archive metadata
accession for additional native/reference products. This bounded attempt closes
with zero empirical PSFs built and zero injection trials. It does not assert
there are no suitable stars in the physical field. Native DQ or another valid
unsaturation check, independent point-source identity, and a separate held-out
PSF residual control would allow a future frozen acquisition. The original
three failed structured-light gates and association failure remain unchanged.

## Verification and not run

JSON parsing, hashes of both compact inputs, response-body hash, path existence,
freeze-before-query chronology, budget/disk checks and arithmetic checks on the
five existing comparison rows pass; machine receipt:
[e_acceptance.json](../research_output/flux_deficit_20261015/e_acceptance.json).
No persistent science/acquisition code was added. No full software quality gate
was run by this arm; integration belongs to root.

Not run: exhaustive current archive inventory; verified G235H programme/product
accession; new science downloads; G235H measurement; native SMACS DQ checks;
stellar crossmatch; PSF construction, validation or injection recovery; new-epoch
photometry; raw known-answer replay/fitter repair; A-law extrapolation; any
holdout access; scientific grade changes or independent cross-lineage audit.

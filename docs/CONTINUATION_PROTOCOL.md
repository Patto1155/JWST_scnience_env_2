# Native-spectrum and deep-imaging continuation

The authoritative incoming baseline is master
`1b4012e326664ce2a3ec5a515b5a832138aba46b` (PR #29). Read
`TAKEOVER_STATUS.md`, `HANDOVER.md`, and `FINAL_RESEARCH_REPORT.md` in that order.
Historical catalogs remain provenance, not newly validated astrophysical sources.

## Ownership and dependencies

Eight specialist roles operate in isolated worktrees. Six workers run at once;
enrichment and adversarial review rotate into freed slots. The coordinator owns
integration, exact baseline reproduction, review resolution, PR publication and
final interpretation. Workers commit focused changes but do not merge them.

| Specialist | Branch suffix | Owned experiment | Dependencies and independent checks |
|---|---|---|---|
| Astrometry | `astrometry` | Distinct SMACS F444W dither; coordinates, coverage, persistence | Verified original image pins; PSF/noise review |
| Calibrated photometry | `photometry` | Deep multiband GOODS 98/254/46 forward modeling | Public cutout/PSF receipts; real-source and astrometry controls |
| Real-source validation | `real_sources` | Frozen grouped controls in deep footprints | Original DR4 labels; report targeted footprint and shared contributors |
| PSF and correlated noise | `psf_noise` | SMACS noise tails, angular-aperture covariance and negative controls | Original images; separately acquired repeat; no GOODS factor transfer |
| Spectroscopy | `spectroscopy` | Native nod/group extraction, trace, pathloss and empirical covariance | Nine pinned CAL products; shared background contributor audit |
| Stellar enrichment | `enrichment` | Atomic-conditioned yield/formation predictions and degeneracy tests | Merged spectral and atomic contracts; explicit ionization/retention assumptions |
| Literature/data acquisition | `literature` | Versioned atomic emissivity and photoionization models | Primary documentation; preserve unsupported lines and model-grid boundaries |
| Adversarial review | `review` | Independent reproduction and counterexamples | Frozen branches/artifacts; review before merging science changes |

Branch names use the prefix `codex/continuation-`. Later experiments must identify
the merged revision or explicitly label a provisional dependency. Native nods,
alternative extractions and overlapping deep cutouts are never multiplied as
independent likelihoods. Signed fluxes and full covariance are preserved.

## Bounded acquisition

Reuse cached public products only after comparing actual bytes with pinned
inventories. New imaging has an aggregate 500 MiB ceiling: up to 150 MiB is
allocated to a distinct SMACS F444W dither and up to 100 MiB to small GOODS
multiband cutouts. Versioned atomic/photoionization inputs have a separate
100 MiB ceiling. Additional allocation requires coordinator accounting against
these ceilings; this is not permission to buy data or observations.

Large inputs and full trial arrays remain outside git. Commit manifests, exact
URLs, version/identity checks, byte/hash receipts, acquisition CLIs, compact
measurements and reproducible commands. A data-dependent selection must be
described as such; a successful checksum is not scientific calibration.

## Evidence and release gates

Keep observations, instrument assumptions, conditional inference and speculation
separate. Ionic emissivity is not an ionization correction. Modeled PSFs are not
empirical galaxy totals. Blank-aperture core scatter cannot certify five-sigma
tails; targeted cutouts cannot establish population completeness. A prompt
formation history and a cosmological population likelihood require different
data and must remain separate.

Before merging, run focused scientific controls, independently inspect the
measurement/uncertainty contract, and run the integrated Python 3.12 quality
gate. Record any external dependency without substituting synthetic observations.
Follow-up rounds operate on merged results and retain earlier snapshots.

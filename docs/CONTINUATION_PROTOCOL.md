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

## Executed continuation rounds

The initial incoming baseline was reproduced before extension. Rotations kept
no more than six specialist workers active with the coordinator, while retaining
eight distinct responsibilities. Published result branches are separate from
worker branches; the GitHub Git-object connector preserved reviewed committed
file deltas when anonymous fetch worked but authenticated command-line push did
not. Science publication did not modify the research-worker runtime sandbox.

| Round | Owned follow-ups and merged-input dependencies | Independent validation |
|---|---|---|
| Baseline | Coordinator; exact master PR #29 images/native hashes, fresh GOODS pixels, coadd scans and compact replay | Locked gate and byte/numerical controls |
| Native and deep observations | Astrometry: distinct SMACS repeat; PSF: field noise/tails; real sources: frozen deep controls; photometry: data then spatial models; spectroscopy: nine CAL signed extraction; literature: atomic/Cue; enrichment: full-covariant mixtures | Actual hashes/units/contributors; reviewer raw-native rerun, latent GLS and independent atomic/NNLS solvers |
| Measured sensitivity and recovery | Spectroscopy: spatial covariance after native; literature: native chemistry after atomic/native; real sources: observed-profile injections after controls; photometry: atmosphere after calibrated deep flux; PSF:1043 patch after repeat/noise | Actual replay, SVD/cluster oracle, independent author-table parsing, paired trial audit |
| Physical contracts and formation | Literature: physical v1 multiplets then separate N IV doublet v2; enrichment: formation after native chemistry/yields; spectroscopy: original-GWCS toy-reference sensitivity after shared-noise transport | Fresh per-template covariance, independent full-native GLS/Fieller, quadrature/conservation, exact original9CAL WCS |
| Final bounded composition | Literature: v2 doublet × original/toy wavelength × three noise hypotheses after both inputs merge; enrichment: v2 yield bridge with each fresh covariance; reviewer: frozen approvals/receipts; coordinator: clean gate and current report | Independent constrained profiles and full-native solver; original defaults stay unchanged; alternate hypotheses never pooled |

Review found and resolved a deep blank-control companion-offset bug, an
injection annulus corner bug, brittle last-bit numerical replay assertions,
a historical atmosphere prose count, and an uninitialized science-array
surrogate in the new compact wavelength loader. Scientific reruns or explicit
unchanged-data checks precede merge; these defects are not left as caveats.

## Acquisition and recovery ledger

Newly selected public scientific inputs for this continuation total
**228,790,074 bytes**: distinct SMACS120,254,400; deep multiband/atmosphere
47,882,944; PyNeb/Cue60,636,277; logged wavelength reference 16,453. Reused
PSFs and existing native data are not counted again. Optional WCS software and
inspected algorithm source total 3,425,987payload bytes and are separately
receipted, including a superseded wheel. No purchased observation or account
mutation was required.

A late transient cache loss required restoring the exact locked environment and
nine previously pinned CAL originals. Repeated native transfer was464,135,040
bytes under the native acquisition ceiling; original pins and derivative audits
matched. `research_output/native_cache_recovery.json` records that recovery.
The lost earlier13-image cache is not represented as presently available; its
completed baseline pixel rerun and committed independent reviews survived.

A full public Cloudyc23.01 source archive is approximately323MB and exceeds the
separate100MiB atomic allocation. It was not downloaded. A complete N IV-inclusive
photoionization output subset or an explicitly larger bounded modeling round
remains unfinished computational work, distinct from missing author extraction
settings or new higher-resolution observations.

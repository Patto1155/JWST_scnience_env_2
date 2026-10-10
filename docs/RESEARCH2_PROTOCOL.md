# Second autonomous research continuation

10 October 2026. Live `origin/master` was fetched before reading local science.
It is exactly `379ff35786aff31535335bbe7d1de114f91dd3c4` (PR #54); the supplied
handover revision is its own ancestor and there are no subsequent commits.
All eight specialist worktrees and the coordinator start there. No existing
working files were overwritten. The earlier continuation protocol and scientific
contracts remain historical records; this protocol governs the new round.

## Ownership, dependencies and review

Six specialist slots run concurrently; enrichment and adversarial review rotate
into freed slots. Branches are `codex/research2-ROLE`. Workers commit focused
changes; the coordinator publishes PRs and merges only after independent
scientific validation and CI. Reviewers may use alternate solvers, primary
input parsing and explicit counterexamples. Passing the author's tests alone
does not validate the scientific measurement.

| Role | Owned work | Dependencies / independent validator |
|---|---|---|
| Astrometry | Public PIXTAB/extraction/calibration provenance; independent archive coverage | Spectroscopy inspects author table/operator; adversarial review checks provenance |
| Photometry | Broader source 46 atmosphere/multiplicity and candidate diagnostics | Pinned deep inputs; reviewer independently parses model tables and solves fits |
| Real sources | Geometry-frozen representative selection pilot with color/morphology/count variation | Photometry restores PSFs; PSF specialist checks design and response; reviewer audits trials |
| PSF / noise | Three-group common systematic identifiability and interval coverage | Native likelihood and signed nod contracts; spectroscopy and reviewer check algebra |
| Spectroscopy | Native measurement injections, group prediction, geometry/line-model alternatives | Astrometry supplies public settings; PSF/reviewer independently solve measurement operator |
| Literature / models | Complete nitrogen-inclusive Cloudy thermal-balance pilot | Versioned native likelihood; enrichment/reviewer validate line mapping, convergence and normalization |
| Enrichment | Complete-model identifiability and discriminating observation predictions | Merged model/spectral pilots; separate reviewer checks likelihood and observation arithmetic |
| Adversarial review | Frozen-input independent validation and rejection tests | All science pilots; authors resolve defects before publication |

## Questions, budgets and stopping

Each experiment records its question, competing predictions, expected information
gain, acquisition/computation budget and stopping rule before examining its
outputs. Prioritize dominant uncertainty and real missing inputs over larger
conditional parameter grids. Three dependency-driven rounds are required:

1. Baseline reproduction, bounded pilots and independent validation.
2. Revised experiments on merged pilot results, including new public inputs
   when they resolve an identified ambiguity.
3. Integrated interpretation, independently reproduced release checks,
   uncertainty budget and ranked feasible follow-ups.

The initial aggregate new-selected-download cap is **2 GiB**. Allocations below
are ceilings, not spending targets. All actual public scientific/model payloads,
failed transfers and runtime-only software transfers are receipted separately.
Nothing authorizes paid resources or contacting people.

| Owner | New selected ceiling |
|---|---:|
| Literature / Cloudy | 600 MiB |
| Spectroscopy / possible lower-stage subset | 350 MiB |
| Astrometry / public settings and archive metadata | 100 MiB |
| Photometry / broader finite model table | 200 MiB |
| Real-source sample | 150 MiB |
| PSF / noise | 100 MiB |
| Enrichment / observation references | 100 MiB |
| Unallocated coordinator reserve | 448 MiB |

Restoration of **already pinned** originals is recorded separately from new
selection: thirteen original images (1,555,571,520 bytes), nine CALs
(464,135,040 bytes), deep cutouts/model tables and the distinct SMACS repeat
as needed. Actual hashes and metadata must match before reuse. Shared caches
have explicit owners to prevent duplicated transfer. Large inputs/full trials
stay outside git with bounded executable regenerators and receipts.

## Interpretation and preservation

No source, elemental abundance, polluter or cosmological discovery is established
at the starting point. Dependent CAL nods, alternative reductions and shared
mosaics are never pooled as independent observations. Keep signed fluxes and
full covariance; preserve version 1 and version 2 N IV contracts. DUMMY wavelength
predictions are sensitivities, not empirical calibration. Recomputed thermal
balance is required when changing composition; missing model lines are not zero.

Known-spectrum closure and synthetic coverage characterize a conditional
operator, not empirical calibration. Any output-grid count conversion assumed
because native conversion is missing must be identified as a nuisance; it does
not provide native source-Poisson/drizzle calibration. Grid membership counts
are not posterior probabilities. Candidate diagnostics and a one-field response
pilot do not supply survey completeness, contamination or cosmological odds.

Updated status/report must identify what changed, what was rejected, what remains
assumption-dependent, actual checks/skips, input hashes, acquisition ledger,
merged PRs and executable reproduction commands.

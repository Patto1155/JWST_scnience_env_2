# Version2 N IV doublet contract: a consequential ionic correction

The merged [first multiplet experiment](MOM_NATIVE_MULTIPLET_REFIT.md) preserved
the earlier N IV]1486-only line contract. This new experiment changes that
contract explicitly: **N IV means the total 1483.321+1486.496 doublet flux under
a physical ionic template**. It generates separate version2 atomic and component
grids and refits all 112 native likelihoods. No version1 input, result, default
template or measured group is overwritten or relabelled.

## Inputs, execution and scope

The branch starts from merged revision `2758481`, after multiplet PR #46.
Its four native scenarios retain the same original wavelength/profile geometry,
source-amplitude covariance and empirical off-trace noise transport. The
separate spatial-covariance and toy wavelength-correction experiments are not
combined with this round. Every Te/ne cell gets a fresh line-flux vector and
5×5 covariance before the new summed N IV emissivity is applied.

```bash
# Optional actual regeneration from the separately verified PyNeb1.1.32 runtime.
PYTHONPATH=/path/to/atomic-inputs/pyneb-runtime python -m tools.jwst.niv_doublet_refit \
  --generate-inputs research_output
# Replay needs only committed grids and the existing compact native NPZ.
python -m tools.jwst.niv_doublet_refit
python -m pytest tests/test_niv_doublet_refit.py tests/test_multiplet_refit.py -q
```

The CLI reports `spectral_fits: 112`. The native report is pinned to
`88e3cdbf5b7759eaad84dc21ead0974c38f392292d71ce605fa0f5b5951637ec`
and its unchanged NPZ to
`9412f52afbed589777cf55ad27ca2e93065cb4003be4990debc17503fe097027`.
The original version1 multiplet result is pinned to
`9248284f52552e88fa002351d9b39aec419cc27e76c631ab6cffae2c5e09e929`.
The two new, independently pinned inputs are:

| Artifact | SHA256 |
|---|---|
| `mom_atomic_grid_niv_doublet_v2.json` | `a48ea0076ae9f6ef4d76845644880776c266efce0a281b0866d12889e36b1e0e` |
| `mom_multiplet_components_niv_doublet_v2.json` | `692ce2fe0ca5463708abfa3c232378f3aebe22ff9b96f97d779091d54ac5f474` |

Generation verifies the same two independently frozen N4 atomic members from
the publisher-verified PyNeb wheel. All non-N IV emissivities, transitions and
physical multiplet components remain exactly those in version1. N IV]1483 is a
distinct atomic transition (upper/lower=4/1), while 1486 is 3/1. Its 1486
emissivity reproduces the version1 grid to tight numerical tolerance. Version2
stores both emissivities, normalized physical weights, transitions and parent
grid lineage; the new atomic N IV response is their sum. Consistent replacements
of scientific weights/totals are rejected by independent byte pins.

## The physical effect

At Te=20,000 K and ne=1,000 cm^-3, PyNeb predicts
epsilon(1483)/epsilon(1486)=**1.480924**. The total doublet emissivity is therefore
**2.480924 times** the version1 single-line response. At the same temperature,
the 1483/1486 ratio falls from 1.494 at ne=100 to 0.762 at ne=100,000 cm^-3.
The omitted component is physically important across this prescribed grid.

It is incorrect to divide a fitted doublet total by a single-line emissivity.
It is also incorrect merely to apply the new sum to old fluxes: adding the blue
component changes the normalized instrumental template and its fitted flux and
covariance. This experiment makes both changes together. The separately stored
version1 flux is still the flux of its original assumed response, not a new
doublet measurement.

## Executed conditional results

At the fixed reference cell Te=20,000 K/ne=1,000 cm^-3:

| Native scenario | Version1 ionic N/C | Version2 ionic N/C | Version2 conditional Gaussian 95% Fieller set |
|---|---:|---:|---|
| Nominal/shared formal | 7.1913 | 3.1679 | [0.9005,6.6821] |
| Point/shared formal | 6.5422 | 2.7845 | [0.6250,6.0940] |
| Nominal/empirical transport | 7.1092 | 3.1274 | [-0.3159,10.6041] |
| Point/empirical transport | 6.4509 | 2.7504 | [-0.5064,9.5916] |

The point/empirical version1 interval was [0.2601,21.1594]. Its version2
counterpart admits zero and the solar ionic number ratio 10^-0.60. Across the
28 prescribed Te/ne cells, **all 28 point/empirical** and **26 nominal/empirical**
Fieller sets cross zero. The two nominal/empirical exceptions are ne=100,000
at Te=5,000/7,500 K. Both formal-covariance families have positive lower
endpoints in every cell; this difference is a noise-model sensitivity rather
than grounds for selecting the smaller formal uncertainty.

For point/empirical noise, central ionic logarithms relative to solar span
0.996–1.398 dex, **not a confidence interval**. Compared cell by cell with
version1, they fall by 0.161–0.439 dex. These positive central values do not
establish an ionic enhancement: their signed uncertainties admit zero across
the whole sampled family. Negative Fieller endpoints are retained as a property
of the signed flux likelihood and are not logged as physical abundances.

| Reference-cell quantity | Nominal empirical | Point empirical |
|---|---:|---:|
| Version1 assumed N IV group flux | 27.4511 | 16.7769 |
| Version2 fitted doublet total flux | 25.6298 | 13.6847 |
| Version2 conditional N IV sigma | 13.7453 | 9.0207 |
| New minus old conditional chi² | +0.5909 | +1.2166 |

Fluxes and sigmas use 1e-20 erg s^-1 cm^-2. These slightly worse conditional
fit objectives do not exclude physical 1483 emission: source wavelength/LSF,
geometry, transfer, continuum and noise assumptions remain fixed and incompletely
calibrated. The data have weak leverage on the doublet components. No density
posterior or model odds are assigned from these deterministic cells.

## Checks, rejected shortcut and unresolved questions

Tests require unchanged version1 bytes, exact version2 lineage/transition/unit
contracts and positive normalized physical weights. A counterexample with equal
true ionic abundances yields a false ratio of 1.75 if the doublet total is divided
by a single-line emissivity, versus the correct ratio 1. Every saved ratio and
Fieller endpoint is independently projected from its own fresh five-group
covariance. A model forgery that preserves totals and weight consistency still
fails the frozen input pins. The original default-template replay also remains
an execution control, distinct from raw-pixel recalibration.

The shortcut that the 1486-only ionic map can calibrate a physical full-doublet
abundance is rejected. The observations still do not separate He II/O III].
C IV transfer/stellar contamination and source-specific LSF/wavelength/profile
calibration remain unknown. Neither ionization fraction is measured, so
elemental N/C = observed-two-stage ionic N/C × f_C/f_N remains unidentified.
Cue still omits N IV] and cannot provide the missing complete map. Shared
observations and versioned alternative fits are not independent likelihoods.
No stellar polluter, galaxy-formation mechanism or cosmology is established.

The next experiments should compose these **version2** templates with independently
reviewed spatial covariance and instrumental wavelength sensitivities, profile
explicit He/O and C IV-transfer alternatives, and obtain an N IV]-inclusive
composition-aware photoionization grid. Conditional yield comparisons should
consume the new covariance and explicit doublet definition rather than reuse
version1 amplitudes or assume an ionization correction.

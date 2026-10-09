"""Render the line-sensitivity JSON into an auditable report and scientific plot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .line_sensitivity import LINE_NAMES, read_extractions  # noqa: E402


def render_report(result_path: Path, spectrum_path: Path) -> None:
    result = json.loads(result_path.read_text())
    scenarios = result["fixed_published_redshift_scenarios"]
    baseline = scenarios[0]
    scan = result["tied_redshift_width_scans"][0]
    ratios = [s["nitrogen_lines_over_carbon_lines"]["value"] for s in scenarios]
    exts, _ = read_extractions(spectrum_path)
    plot_path = result_path.with_suffix(".png")
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), gridspec_kw={"height_ratios": [2.3, 1.3]})
    e = exts[0]
    usable = e.valid & (e.wave >= 2.15) & (e.wave <= 3.2)
    axes[0].errorbar(
        e.wave[usable],
        e.flux[usable],
        e.error[usable],
        fmt=".",
        ms=3,
        color=".35",
        alpha=0.65,
        label="Stored pixel-table 1D, diagonal errors",
    )
    axes[0].plot(
        e.wave[usable],
        np.array(baseline["model_fnu_uJy"])[usable],
        color="#204c78",
        lw=1.7,
        label="Nominal illuminated-slit LSF + tied UV groups",
    )
    alternate = next(
        s
        for s in scenarios
        if s["extraction"] == "2d_profile_plus_background_r3" and s["rho_assumed"] == 0
    )
    ae = next(ext for ext in exts if ext.name == alternate["extraction"])
    axes[0].plot(
        ae.wave[usable],
        ae.flux[usable],
        color="#ad7332",
        alpha=0.65,
        lw=0.8,
        label="2D profile + per-column background nuisance",
    )
    axes[0].set(
        xlabel="Observed wavelength (µm)",
        ylabel="Flux density (µJy)",
        title="MoM-z14 public DJA extraction: assumption sensitivity, no abundance fit",
    )
    axes[0].legend(fontsize=8, loc="upper right")
    chosen = [
        scenarios[0],
        scenarios[2],
        next(s for s in scenarios if s["extraction"] == "2d_optimal_r3" and s["rho_assumed"] == 0),
        alternate,
    ]
    for offset, (s, color, label) in enumerate(
        zip(
            chosen,
            ["#204c78", "#95548f", "#4b885d", "#ad7332"],
            ["Stored, ρ=0", "Stored, assumed ρ=0.5", "2D optimal ±3", "2D profile + background"],
        )
    ):
        x = np.arange(5) + (offset - 1.5) * 0.16
        axes[1].errorbar(
            x,
            [s["lines"][n]["flux"] for n in LINE_NAMES],
            [s["lines"][n]["conditional_sigma"] for n in LINE_NAMES],
            fmt="o",
            color=color,
            ms=4,
            capsize=2,
            label=label,
        )
    axes[1].axhline(0, color=".5", lw=0.7)
    axes[1].set_xticks(np.arange(5), ["N IV]", "C IV", "He II + O III]", "N III]", "C III]"])
    axes[1].set_ylabel("Flux (10⁻²⁰ erg s⁻¹ cm⁻²)")
    axes[1].legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    rows = [
        "# MoM-z14: UV-line and extraction sensitivity",
        "",
        "The public DJA spectrum supports a reproducible conditional UV-line fit, but it does not identify an enrichment mechanism or measure elemental N/C. Extraction/background and source-specific LSF remain material limitations. All numerical values below come from actual FITS samples.",
        "",
        "## Inputs and calibration",
        "",
        f"Source SHA256: `{result['metadata']['input_sha256']}`. MsaExp version: `{result['metadata']['msaexp_version']}`. The 473-bin PRISM/CLEAR product has SCI/WHT/PROFILE/BACKGROUND, but no exposure DQ or PIXTAB. Stored SPEC1D prefers the original unresampled pixel-table extraction.",
        "",
        "[The exact MsaExp generator](https://github.com/gbrammer/msaexp/blob/e2b237b/msaexp/slit_combine.py) divides science by pathloss and variance by pathloss² before resampling. SCI is nod-differenced, BACKGROUND is a separate sky estimate, and PROFILE has signed negative nod ghosts. Our alternatives use the central profile, propagate WHT=1/variance, and apply neither a second path correction nor a second sky subtraction. The optional spatially constant background is fitted as a nuisance in each wavelength column, with its covariance propagated.",
        "",
        "[STScI's tabulated PRISM resolving power](https://jwst-docs.stsci.edu/jwst-near-infrared-spectrograph/nirspec-instrumentation/nirspec-dispersers-and-filters) supplies wavelength-dependent R=61.4–97.7 across these groups. Its nominal 2.2-pixel fully illuminated aperture is approximated with a Gaussian; it is **not** a source-specific calibrated point-source LSF. A ±30% FWHM scaling is a sensitivity check, not a calibration posterior.",
        "",
        "## Model and masks",
        "",
        "The fixed 2.15–3.20 µm window has 73 usable bins. Finite flux, positive finite errors, npix, profile_sum, var_sum and path_corr define the stored mask. Alternatives require valid SCI/WHT/PROFILE, at least two valid spatial rows and ≥95% of the modeled aperture support. No flux/SNR-dependent rejection is applied. Original full-grid bin edges remain unchanged when a bin is masked.",
        "",
        "Five signed integrated line amplitudes are fit jointly with a smooth polynomial continuum in fν. Gaussians are integrated over bins, convolved by quadrature with instrumental FWHM and a shared intrinsic FWHM. Redshift and width are tied across groups. Multiplet weights and the He II/O III] decomposition are explicit assumptions. We retain negative estimates rather than imposing a positivity prior. Formal errors include linear continuum covariance; redshift/width profile intervals are saved separately.",
        "",
        "## Results at published z=14.44",
        "",
        "All fluxes are 10⁻²⁰ erg s⁻¹ cm⁻². ± values are conditional one-sigma GLS errors, not independently calibrated detection significances.",
        "",
        "| Scenario | N IV] | C IV | He II + O III] | N III] | C III] | (N IV]+N III])/(C IV+C III]) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in scenarios:
        label = f"{s['extraction']}; ρ={s['rho_assumed']:g}; LSF×{s['lsf_fwhm_multiplier']:g}; width={s['intrinsic_fwhm_km_s']:g}; cont={s['continuum_fnu_polynomial_order']}; {s['blend_assumption']}"
        values = [
            f"{s['lines'][n]['flux']:.2f} ± {s['lines'][n]['conditional_sigma']:.2f}"
            for n in LINE_NAMES
        ]
        rows.append(
            "| "
            + " | ".join([label, *values, f"{s['nitrogen_lines_over_carbon_lines']['value']:.3f}"])
            + " |"
        )
    ratio = baseline["nitrogen_lines_over_carbon_lines"]
    interval = ratio["fieller_normal_68_and_95_sets"]["1.95996398454"]["interval"]
    rows += [
        "",
        f"The baseline line-flux ratio is {ratio['value']:.3f}, with a conditional 95% Fieller interval [{interval[0]:.3f}, {interval[1]:.3f}]. Across all {len(scenarios)} stated scenarios its point estimate spans {min(ratios):.3f}–{max(ratios):.3f}; this range is not a confidence interval. The spatial background-nuisance alternative admits zero/negative nitrogen-line flux at 95%, while its point estimate remains consistent with the baseline within broad errors.",
        "",
        "Increasing intrinsic FWHM from 0 to 650 km/s changes baseline fluxes by <1.1% because the nominal instrument FWHM is roughly 3,000–4,900 km/s. Under this nominal LSF the data do not resolve intrinsic widths in that range. Source illumination and background treatment have larger effects. N III] is a weak conditional estimate in this implementation; this does not refute the published fit, whose calibrated point-source LSF, continuum, prior and extraction handling differ.",
        "",
        "## Redshift scan, covariance and limits",
        "",
        f"The tied UV-group scan over z=14–15 (step 0.005) and intrinsic widths 0/300/650 km/s gives best z={scan['best_fit']['redshift']:.3f}, consistent with the published z=14.44. The Δχ²≤1 profile envelope is {scan['delta_chi2_1_profile_envelope_z']}. This is conditional on the adopted LSF, continuum, blends and covariance and is not a replacement for the published posterior. The best width is on the lower boundary; no resolved width measurement is claimed.",
        "",
        "AR(1) ρ=0, 0.25 and 0.5 are **assumed covariance scenarios**, not measured correlations. With stored diagonal errors χ²=89.99 for 66 degrees of freedom; ρ=0.5 increases it to 186.30/66. Strong assumed positive covariance is thus a poor residual description under this smooth model and should not be promoted as a calibrated uncertainty estimate. None of the scenarios includes unknown spatial covariance or exposure-level reduction systematics.",
        "",
        "A seeded conditional Gaussian-null exercise repeats the full z/width scan for 1,000 simulations. Zero simulated maxima exceed the observed joint signed-template improvement under either tested covariance, so the Monte Carlo resolution is only about 0.001 (plus-one value); it does not establish an exact smaller tail probability. This is a conditional check of joint template structure, not new line discoveries or an astrophysical false-positive rate. The line set and source were selected in previous research; that selection, alternative continua, uncertain LSF and unknown real covariance are outside this null.",
        "",
        "## Relation to published chemistry and rejected shortcuts",
        "",
        "[Naidu et al. v2](https://arxiv.org/html/2505.11263v2) already uses UNITE wavelength-dependent point-source LSF and calibration uncertainty, tied intrinsic widths up to 650 km/s, and multi-Gaussian blends. The old input JSON caveat has been corrected to make that explicit. We reproduce the existence of useful UV constraints under a simpler model, not the exact published posterior. Paper line values remain a separately labelled transcription, not fit inputs.",
        "",
        "Reject these interpretations: a flux ratio of ~1 is not elemental N/C; a line-width boundary is not resolved kinematics; re-extractions sharing the same exposures are not independent confirmations; nominal spectral null tails do not resolve astrophysical identity; nitrogen enhancement is not an age clock for the entire galaxy. No WR, VMS, SMS, AGN, Population III or cosmology mechanism is selected by this experiment.",
        "",
        "## Highest-value next experiments",
        "",
        "1. Acquire original slit/exposure pixel tables with DQ and source-specific LSF/pathloss metadata; compare UNITE-style point-source convolution against the nominal curve and fit independent nod groups. The current file lacks these inputs, so neither exact original extraction nor empirical exposure covariance can be recovered here.",
        "2. Calibrate wavelength and spatial covariance from independent integrations and line-free controls, then fit a residual background model constrained by genuinely off-source pixels. Stored BACKGROUND must not be subtracted again.",
        "3. Obtain higher-resolution spectra resolving N IV], N III], C III] density diagnostics and separating He II from O III]; propagate temperature, density, ionization and atomic emissivity into any abundance/yield comparison.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "OPENBLAS_NUM_THREADS=1 python -m tools.jwst.line_sensitivity",
        "python -m tools.jwst.line_report",
        "python -m pytest -q tests/test_line_sensitivity.py",
        "```",
        "",
        "Known-signal controls independently integrate Gaussian spectra on fine grids, mask a line-center bin without changing its neighbors' bin edges, recover synthetic spatial fluxes and nuisance backgrounds, verify inverse-variance propagation, preserve unbounded Fieller sets for weak denominators, and preserve masked-bin separations in AR covariance. Raw per-scenario fluxes, covariance matrices, model vectors, profile intervals, masks and scan/null results are in the companion JSON.",
        "",
        f"Rerunning `line_report` saves the companion scientific plot as `{plot_path.name}`.",
        "",
    ]
    result_path.with_suffix(".md").write_text("\n".join(rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--result", type=Path, default=Path("research_output/mom_z14_line_sensitivity.json")
    )
    parser.add_argument(
        "--spectrum", type=Path, default=Path("data_sources/pilot/mom_z14_dja_v4.spec.fits")
    )
    args = parser.parse_args()
    render_report(args.result, args.spectrum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

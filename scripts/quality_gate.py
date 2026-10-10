"""Run minimal lint/type/test quality gates."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_TARGETS = [
    "core_api/routers/runs.py",
    "core_api/services/strict_validation.py",
    "core_api/services/run_service.py",
    "run_discovery.py",
    "discovery/batch_runner.py",
    "scripts/smoke_api.py",
]
SCIENCE_LINT_TARGETS = [
    "discovery/psf_noise.py",
    "runner/tests/test_psf_noise.py",
    "data_pipeline/original_images.py",
    "tools/jwst/astrometry.py",
    "discovery/external_astrometry.py",
    "tests/test_external_astrometry.py",
    "discovery/image_photometry_rerun.py",
    "tools/jwst/common_coverage.py",
    "tests/test_image_photometry_rerun.py",
    "tools/jwst/photometry.py",
    "tools/jwst/flux_calibration.py",
    "tools/jwst/dropout.py",
    "discovery/build_universe_table.py",
    "discovery/proposal_channels.py",
    "discovery/multi_epoch.py",
    "tests/test_multi_epoch_physical.py",
    "tools/jwst/spectroscopy.py",
    "tools/jwst/visualization.py",
    "tools/jwst/fits_loader.py",
    "core_api/startup.py",
    "discovery/external_psf_stress.py",
    "discovery/validation_audit.py",
    "discovery/validation_metrics.py",
    "data_pipeline/research_sources.py",
    "data_pipeline/reference_cohorts.py",
    "tests/test_spectrum_reference.py",
    "data_pipeline/followup_data.py",
    "data_pipeline/mom_native_batch.py",
    "data_pipeline/real_validation_acquire.py",
    "data_pipeline/rotating_benchmarks.py",
    "discovery/adversarial_native_inputs.py",
    "discovery/adversarial_noise_controls.py",
    "discovery/chemistry_identifiability.py",
    "discovery/deep_reference_comparison.py",
    "discovery/enrichment_constraints.py",
    "discovery/f444w_repeat_screen.py",
    "discovery/native_psf.py",
    "discovery/photometry_sensitivity.py",
    "discovery/real_validation.py",
    "discovery/stellar_aperture.py",
    "discovery/survivor_continuum.py",
    "runner/tests/test_native_psf.py",
    "runner/tests/test_stellar_aperture.py",
    "scripts/quality_gate.py",
    "tests/test_adversarial_native_operator.py",
    "tests/test_adversarial_noise_controls.py",
    "tests/test_chemistry_identifiability.py",
    "tests/test_deep_reference_comparison.py",
    "tests/test_enrichment_constraints.py",
    "tests/test_f444w_repeat_screen.py",
    "tests/test_followup_data.py",
    "tests/test_joint_band_selection.py",
    "tests/test_line_sensitivity.py",
    "tests/test_mom_native_batch.py",
    "tests/test_photometry_sensitivity.py",
    "tests/test_point_resolution.py",
    "tests/test_real_validation.py",
    "tests/test_survivor_continuum.py",
    "tools/jwst/line_report.py",
    "tools/jwst/line_sensitivity.py",
    "tools/jwst/point_resolution.py",
    "data_pipeline/atomic_inputs.py",
    "data_pipeline/survivor_deep_data.py",
    "discovery/atomic_enrichment.py",
    "discovery/continuation_final_review.py",
    "discovery/continuation_followup_review.py",
    "discovery/continuation_review.py",
    "discovery/covariant_model_review.py",
    "discovery/deep_control_recovery.py",
    "discovery/empirical_imaging_controls.py",
    "discovery/formation_predictions.py",
    "discovery/independent_repeat_vetting.py",
    "discovery/observed_template_injections.py",
    "discovery/source_patch_diagnostics.py",
    "discovery/survivor_atmosphere.py",
    "discovery/survivor_deep_model.py",
    "discovery/survivor_deep_plot.py",
    "scripts/render_repeat_stamp.py",
    "tests/test_atomic_enrichment.py",
    "tests/test_atomic_grid.py",
    "tests/test_continuation_final_review.py",
    "tests/test_continuation_followup_review.py",
    "tests/test_continuation_review.py",
    "tests/test_cue_grid.py",
    "tests/test_deep_control_recovery.py",
    "tests/test_empirical_imaging_controls.py",
    "tests/test_formation_predictions.py",
    "tests/test_independent_repeat_vetting.py",
    "tests/test_mom_native_reduction.py",
    "tests/test_mom_native_spatial_covariance.py",
    "tests/test_multiplet_refit.py",
    "tests/test_native_chemistry.py",
    "tests/test_niv_doublet_refit.py",
    "tests/test_observed_template_injections.py",
    "tests/test_source_patch_diagnostics.py",
    "tests/test_survivor_atmosphere.py",
    "tests/test_survivor_deep_data.py",
    "tests/test_survivor_deep_model.py",
    "tools/jwst/atomic_grid.py",
    "tools/jwst/cue_grid.py",
    "tools/jwst/multiplet_refit.py",
    "tools/jwst/native_reduction.py",
    "tools/jwst/native_spatial_covariance.py",
    "tools/jwst/niv_doublet_refit.py",
    "discovery/niv_yield_sensitivity.py",
    "tests/test_composed_spectral_refit.py",
    "tests/test_mom_native_wavecorr.py",
    "tests/test_niv_yield_sensitivity.py",
    "tools/jwst/composed_spectral_refit.py",
    "tools/jwst/native_wavecorr.py",
    "discovery/continuation_composed_review.py",
    "discovery/continuation_physical_review.py",
    "discovery/continuation_wavecorr_review.py",
    "discovery/continuation_yield_version_review.py",
    "tests/test_continuation_physical_review.py",
    "tests/test_continuation_wavecorr_review.py",
    "tests/test_continuation_yield_version_review.py",
]
RESEARCH2_SCIENCE_LINT_TARGETS = [
    "discovery/research2_cloudy_grid_rate_review.py",
    "tests/test_cloudy_grid_rate_review.py",
    "tools/jwst/cloudy_atomic_provenance.py",
    "tools/jwst/cloudy_raw_archive.py",
    "tests/test_cloudy_raw_archive.py",
    "discovery/research2_capers_source_review.py",
    "tests/test_capers_source_review.py",
    "data_pipeline/capers_companion_coverage.py",
    "tests/test_capers_companion_coverage.py",
    "data_pipeline/capers_s2d_coverage.py",
    "tests/test_capers_s2d_coverage.py",
    "data_pipeline/cloudy_inputs.py",
    "data_pipeline/mom_author_provenance.py",
    "data_pipeline/capers_pixtab_coverage.py",
    "tests/test_capers_pixtab_coverage.py",
    "data_pipeline/mom_compact_followup.py",
    "tests/test_mom_compact_followup.py",
    "data_pipeline/mom_public_metadata.py",
    "tests/test_mom_public_metadata.py",
    "data_pipeline/observation_design_inputs.py",
    "discovery/candidate_neighborhood.py",
    "discovery/research2_cloudy_rate_bridge_review.py",
    "tests/test_cloudy_rate_bridge_review.py",
    "discovery/research2_cloudy_backend_review.py",
    "discovery/research2_cloudy_capped_review.py",
    "discovery/research2_cloudy_composition_review.py",
    "discovery/research2_cloudy_design_review.py",
    "discovery/research2_cloudy_heldout_review.py",
    "discovery/research2_cloudy_likelihood_review.py",
    "discovery/research2_cloudy_model_review.py",
    "discovery/research2_flame_review.py",
    "discovery/research2_independent_review.py",
    "discovery/research2_medium_review.py",
    "discovery/research2_neighborhood_review.py",
    "discovery/research2_observation_review.py",
    "discovery/research2_prediction_review.py",
    "discovery/research2_download_ledger.py",
    "tests/test_research2_download_ledger.py",
    "discovery/research2_release_review.py",
    "tests/test_research2_release_review.py",
    "discovery/research2_compact_followup_review.py",
    "discovery/research2_local_identifiability_review.py",
    "discovery/research2_public_metadata_review.py",
    "discovery/research2_rate_noise_review.py",
    "discovery/research2_row_response_review.py",
    "discovery/research2_selection_count_review.py",
    "discovery/research2_selection_receipt.py",
    "discovery/research2_signed_response_review.py",
    "discovery/selection_count_audit.py",
    "discovery/selection_pilot.py",
    "discovery/survivor46_medium.py",
    "discovery/survivor46_medium_plot.py",
    "discovery/survivor_flame.py",
    "discovery/survivor_multiplicity.py",
    "tests/test_candidate_neighborhood.py",
    "tests/test_cloudy_observation_contrasts.py",
    "tests/test_cloudy_pilot.py",
    "tests/test_mom_author_provenance.py",
    "tests/test_native_measurement_validation.py",
    "tests/test_native_rate_noise.py",
    "tests/test_native_row_response.py",
    "tests/test_observation_design.py",
    "tests/test_research2_cloudy_composition_review.py",
    "tests/test_research2_cloudy_heldout_review.py",
    "tests/test_research2_cloudy_likelihood_review.py",
    "tests/test_research2_cloudy_model_review.py",
    "tests/test_research2_independent_review.py",
    "tests/test_research2_model_review.py",
    "tests/test_selection_count_audit.py",
    "tests/test_selection_pilot.py",
    "tests/test_shared_systematics.py",
    "tests/test_survivor46_medium.py",
    "tests/test_survivor_flame.py",
    "tests/test_survivor_multiplicity.py",
    "tools/jwst/acquire_rate_noise_inputs.py",
    "tools/jwst/cloudy_observation_contrasts.py",
    "tools/jwst/cloudy_pilot.py",
    "tools/jwst/native_measurement_validation.py",
    "tools/jwst/native_local_identifiability.py",
    "tests/test_native_local_identifiability.py",
    "tools/jwst/native_rate_noise.py",
    "tools/jwst/native_row_response.py",
    "tools/jwst/observation_design.py",
    "tools/jwst/shared_systematics.py",
]


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _run_step(name: str, cmd: list[str]) -> bool:
    print(f"[QUALITY] {name}: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"[QUALITY][FAIL] {name} (exit={result.returncode})", flush=True)
        return False
    print(f"[QUALITY][OK] {name}", flush=True)
    return True


def main() -> int:
    ok = True

    if not _module_available("ruff") or not _module_available("mypy"):
        print(
            "[QUALITY][FAIL] Missing dev dependencies. "
            "Install with: python -m pip install -r requirements-dev.txt",
            flush=True,
        )
        return 1

    ok &= _run_step(
        "ruff-check",
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "E9,F",
            *CHECK_TARGETS,
            *SCIENCE_LINT_TARGETS,
            *RESEARCH2_SCIENCE_LINT_TARGETS,
        ],
    )
    ok &= _run_step(
        "research2-strict-science-lint",
        [sys.executable, "-m", "ruff", "check", "--select", "E,F,I",
         *RESEARCH2_SCIENCE_LINT_TARGETS],
    )
    ok &= _run_step(
        "ruff-format-check",
        [sys.executable, "-m", "ruff", "format", "--check", *CHECK_TARGETS],
    )
    ok &= _run_step(
        "mypy",
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=silent",
            "--ignore-missing-imports",
            "--no-strict-optional",
            "--disable-error-code=import-untyped",
            "run_discovery.py",
            "discovery/batch_runner.py",
            "scripts/smoke_api.py",
        ],
    )
    ok &= _run_step(
        "pytest",
        [sys.executable, "-m", "pytest", "-q"],
    )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

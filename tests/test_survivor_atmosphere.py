"""Physical table-identity, logarithmic units and GLS predictive controls."""

import numpy as np
import pytest

from discovery.survivor_atmosphere import BANDS, fit_grid, parse_table


def author_table(header=None, row=None):
    prefix = (
        "Fluxes from a synthetic analytic control\n"
        "*** These are log(fluxes) (in mJy) computed for d=  10.00pc   ***\n"
    )
    filters = list(BANDS) if header is None else header
    numeric = "400 4.0 5.1 .1* .28 -99 " + " ".join(["-3"] * len(filters))
    return (
        prefix
        + "Teff log g mass R/Rsun Y log Kzz "
        + " ".join(filters)
        + "\n"
        + (numeric if row is None else row)
        + "\n"
    )


def test_actual_header_log_mjy_conversion_and_radius_flag():
    rows = parse_table(author_table(), {"table_member": "control"})
    assert rows[0]["flux_njy_at_10pc"] == pytest.approx([1000] * len(BANDS))
    assert rows[0]["radius_author_flag"] is True
    assert rows[0]["model_radius_rsun"] == 0.1
    assert rows[0]["teff_k"] == 400


def test_filename_cannot_substitute_for_actual_filter_or_units():
    with pytest.raises(ValueError, match="required JWST"):
        parse_table(author_table(["Y", "Z", "J", "H", "K"]), {})
    with pytest.raises(ValueError, match="units"):
        parse_table(author_table().replace("(in mJy)", "Vega magnitudes"), {})
    with pytest.raises(ValueError, match="lengths differ"):
        parse_table(author_table(row="400 4 .1 .1 .28 -99 -2"), {})


def test_author_column_reordering_preserves_filter_identity():
    reverse = list(reversed(BANDS))
    numbers = [str(-i) for i in range(1, 8)]
    text = author_table(reverse, "400 4 5 .1 .28 -99 " + " ".join(numbers))
    row = parse_table(text, {})[0]
    assert row["flux_njy_at_10pc"] == pytest.approx(list(10.0 ** np.arange(-7, 0) * 1e6))


def test_covariant_positive_amplitude_grid_fit_and_prediction():
    model1 = np.array([1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0])
    model2 = np.array([2.0, 3.0, 5.0, 9.0, 17.0, 33.0, 64.0])
    grid = [{"flux_njy_at_10pc": model1.tolist()}, {"flux_njy_at_10pc": model2.tolist()}]
    flux = 0.02 * model1
    covariance = np.diag(np.linspace(0.1, 0.3, 7)) + 0.04 * np.ones((7, 7))
    fitted = fit_grid(flux, covariance, grid)
    assert fitted[0]["model_flux_njy"] == pytest.approx(flux)
    assert fitted[0]["chi2_conditional"] < 1e-25
    assert fitted[0]["distance_pc_if_model_radius_single_object"] == pytest.approx(
        10 / np.sqrt(0.02)
    )
    retained = np.arange(6)
    held = fit_grid(flux, covariance, grid, retained)[0]
    assert held["model_flux_njy"][-1] == pytest.approx(flux[-1])
    changed_held_flux = flux.copy()
    changed_held_flux[-1] *= 1000
    assert fit_grid(changed_held_flux, covariance, grid, retained)[0][
        "model_flux_njy"
    ] == pytest.approx(held["model_flux_njy"])
    negative = fit_grid(-flux, covariance, grid)[0]
    assert negative["f444_amplitude_njy"] == 0
    assert negative["distance_pc_if_model_radius_single_object"] is None

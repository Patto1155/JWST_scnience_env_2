"""Actual line-contract rejection controls; no missing flux is zero-filled."""

import json

import pytest

from discovery.research2_cloudy_model_review import (
    BLENDS,
    UV_GROUPS,
    actual_deck_environment,
    complete_pilot20_audit,
    pilot20_parameters,
    read_actual_line_dictionary,
)


def make_table(tmp_path):
    names = (
        [line for group in UV_GROUPS for line in group]
        + list(BLENDS)
        + [
            "H 1 4861.32A",
            "O 3 5006.84A",
            "N 2 6583.45A",
            "N 5 1238.82A",
            "N 5 1242.80A",
            "C 2 2323.50A",
            "C 2 2324.69A",
            "C 2 2325.40A",
            "C 2 2326.93A",
            "C 2 2328.12A",
        ]
    )
    values = [1.0] * 29
    for i, group in enumerate(UV_GROUPS):
        values[14 + i] = float(len(group))
    expected = []
    for name in names:
        label, wave = name.rsplit(" ", 1)
        expected.append((label, float(wave[:-1])))
    path = tmp_path / "actual.lin"
    path.write_text(
        "#lineslist\t" + "\t".join(names) + "\niteration 3\t" + "\t".join(map(str, values)) + "\n"
    )
    return path, expected


def test_complete_independent_multiplet_sums_and_reject_bad_blend(tmp_path):
    path, expected = make_table(tmp_path)
    values, sums = read_actual_line_dictionary(path, expected)
    assert sums.tolist() == [2.0, 2.0, 3.0, 5.0, 2.0]
    path.write_text(path.read_text().replace("5.0", "4.0"))
    with pytest.raises(ValueError, match="summed"):
        read_actual_line_dictionary(path, expected)


def test_ordered_actual_line_identity_rejects_swapping_members(tmp_path):
    path, expected = make_table(tmp_path)
    content = path.read_text().replace("N 4 1483.32A", "placeholder")
    content = content.replace("N 4 1486.50A", "N 4 1483.32A")
    content = content.replace("placeholder", "N 4 1486.50A")
    path.write_text(content)
    with pytest.raises(ValueError, match="identity"):
        read_actual_line_dictionary(path, expected)


def test_actual_input_environment_rejects_wrong_density_and_double_z(tmp_path):
    path = tmp_path / "actual.in"
    deck = """blackbody 60000 K
ionization parameter -2
hden 3
abundances GASS10
metals 0.2 linear
element oxygen abundance -3.30980391997
element carbon abundance -3.67980391997
element nitrogen abundance -4.27980391997
radius 19
sphere
CMB redshift 14.44
stop efrac -2
stop temperature 1000 K
stop zone 3000
iterate to convergence
"""
    path.write_text(deck)
    parameters = {
        "blackbody_K": 60000.0,
        "log_U": -2.0,
        "log_nH_cm3": 3.0,
        "metallicity_scale": 0.2,
        "log_NC_relative_minus060": 0.0,
    }
    assert actual_deck_environment(path, parameters) == deck
    path.write_text(deck.replace("hden 3", "hden 4"))
    with pytest.raises(ValueError, match="log_nH"):
        actual_deck_environment(path, parameters)
    path.write_text(deck.replace("-3.30980391997", "-4.00877392431"))
    with pytest.raises(ValueError, match="unscaled"):
        actual_deck_environment(path, parameters)


def test_partial_and_duplicate_pilot_cannot_be_complete(tmp_path):
    expected = pilot20_parameters()
    assert len(expected) == 20
    assert {p["log_nH_cm3"] for p in expected} == {2.0, 3.0, 4.0, 5.0}
    assert {p["blackbody_K"] for p in expected} == {40000.0, 60000.0, 100000.0}
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"models": []}))
    with pytest.raises(ValueError, match="twenty"):
        complete_pilot20_audit(path, tmp_path)
    models = [{"id": f"model{i:03d}", "parameters": p} for i, p in enumerate(expected)]
    models[2]["parameters"] = models[0]["parameters"]
    path.write_text(json.dumps({"models": models}))
    with pytest.raises(ValueError, match="controls"):
        complete_pilot20_audit(path, tmp_path)

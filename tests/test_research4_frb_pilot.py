"""Protect event identity and predeclared coverage stops in the FRB pilot."""

from discovery.research4_frb_pilot import covariance, quality, screen


def row(event: str = "1", source: str = "FRB_TEST") -> dict[str, str]:
    return {
        "event_id": event,
        "repeater_name": source,
        "sub_num": "0",
        "excluded_flag": "0",
        "sidelobe_flag": "0",
        "intrachan_flag": "0",
        "catalog1_param_flag": "0",
        "snr_fitb": "30",
        "dm_fitb": "100",
        "dm_fitb_err": "0.1",
        "scat_time": "0.02",
        "scat_time_err": "0.001",
        "peak_freq": "600",
        "low_freq": "400",
        "high_freq": "800",
        "mjd_inf": "60000",
    }


def test_zero_model_is_not_a_scattering_measurement() -> None:
    r = row()
    r["scat_time"] = "0"
    assert quality(r) == "not_positive_scattering_or_error"
    r["scat_time_err"] = ""
    assert quality(r) == "missing_numeric"


def test_subbursts_do_not_supply_independent_replication() -> None:
    rr = [row(str(i), "ONE_SOURCE") for i in range(6)]
    rr += [dict(rr[0], sub_num="1")]
    out = screen(rr)
    assert out["unique_events"] == 6
    assert out["selected_events"] == 5
    assert out["status"] == "coverage_stop"
    assert not out["outcome_associations_computed"]
    rr[-1]["dm_fitb"] = "101"
    assert screen(rr)["status"] == "schema_stop"


def test_covariance_has_null_correlation_for_constant_values() -> None:
    out = covariance([row("1"), row("2"), row("3")])
    assert out["sample_covariance"] == 0
    assert out["pearson_r"] is None
    assert abs(out["delta_method_random_error_covariance_bound"] - 0.005) < 1e-12


def test_time_halves_are_deterministic_with_odd_source_count() -> None:
    rr = []
    for s in range(6):
        for i in reversed(range(7)):
            r = row(f"s{s}_{i}", f"S{s}")
            r["mjd_inf"] = str(60000 + i)
            r["dm_fitb"] = str(100 + i)
            r["scat_time"] = str(0.02 + 0.001 * i)
            rr.append(r)
    out = screen(rr)
    assert out["status"] == "exploratory_association_only"
    source = out["per_source"]["S0"]
    assert source["early_event_ids"] == ["s0_0", "s0_1", "s0_2"]
    assert source["late_event_ids"] == ["s0_3", "s0_4", "s0_5", "s0_6"]

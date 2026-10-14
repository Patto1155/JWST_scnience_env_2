"""Tests for prospective identity/availability guards, not actual astrophysics."""

import pytest

from discovery.research6_yso_pilot import csv_rows, epoch_inventory, exact_identity


def row(obs, detector, mjd, collection="spherex_qr3"):
    return {
        "obs_id": obs,
        "energy_bandpassname": detector,
        "t_min": str(mjd),
        "obs_collection": collection,
    }


def test_reprocessed_photons_are_not_new_epochs():
    rows = [row("old", "D4", 61270), row("old", "D4", 61270, "spherex_qr4")]
    result = epoch_inventory(rows, {("old", "D4")})
    assert result["unique_physical_exposures"] == 1
    assert result["new_exposures_vs_baseline"] == []
    assert result["metadata_spans_30days"] is False
    assert "not measured" in result["source_W1_coverage"]


def test_original_window_stays_sealed_against_extension():
    result = epoch_inventory([row("new", "D4", 61320)], set())
    assert len(result["new_exposures_vs_baseline"]) == 1
    assert result["new_inside_original_window"] == []


def test_identity_does_not_substitute_ineligible_or_ambiguous_sources():
    good = {"main_id": "AA Tau", "otype": "TT*", "ra": "1", "dec": "2"}
    assert exact_identity([good], "AA Tau")["status"] == "identity eligible"
    assert exact_identity([good, good], "AA Tau")["status"].startswith("blocked")
    assert exact_identity([{**good, "otype": "Galaxy"}], "AA Tau")["status"].startswith("blocked")


def test_service_errors_do_not_become_empty_coverage():
    with pytest.raises(ValueError, match="XML/HTML"):
        csv_rows(b"<html>Service error</html>")
    with pytest.raises(ValueError, match="identity"):
        epoch_inventory([{"t_min": "61270"}], set())


def test_failed_body_is_charged_and_pinned(tmp_path, monkeypatch):
    import hashlib
    import json

    from discovery.research6_yso_pilot import BoundedMetadata

    class Response:
        status_code = 503
        url = "https://official.example/test"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def iter_content(self, _):
            yield b"unavailable"

    monkeypatch.setattr("discovery.research6_yso_pilot.requests.get", lambda *a, **kw: Response())
    client = BoundedMetadata(tmp_path)
    assert client.get("failed", Response.url) is None
    assert client.total == len(b"unavailable")
    receipt = json.loads((tmp_path / "f_failed_receipt.json").read_text())
    assert receipt["sha256_consumed_body"] == hashlib.sha256(b"unavailable").hexdigest()
    assert receipt["error"] == "HTTP 503"


def test_campaigns_do_not_count_dithers_as_independent_visits():
    from discovery.research6_yso_coverage import campaigns

    inputs = [{"mjd_start": x} for x in [61270, 61270.001, 61271, 61320]]
    groups = campaigns(inputs)
    assert [len(g) for g in groups] == [3, 1]


def test_tail_parser_preserves_actual_published_tab_wcs():
    import gzip

    import numpy as np
    from astropy.io import fits
    from astropy.wcs import WCS

    from discovery.research6_yso_coverage_fast import headers_from_ranges
    from discovery.research6_yso_pilot import ROOT

    body = gzip.decompress(
        (ROOT / "research_output/research5_time_spherex_000.fits.gz").read_bytes()
    )
    tail_start = max(0, len(body) - 65536)
    header, table = headers_from_ranges(body[:65536], body[tail_start:], tail_start)
    with fits.open(__import__("io").BytesIO(body)) as original:
        expected = WCS(original["IMAGE"].header, fobj=original, key="W")
        recovered = WCS(header, fobj=fits.HDUList([fits.PrimaryHDU(), table]), key="W")
        points = [[10, 10], [12.1, 11.3], [9.8, 12.7]]
        assert np.allclose(
            expected.wcs_pix2world(points, 0),
            recovered.wcs_pix2world(points, 0),
            rtol=0,
            atol=1e-12,
        )


def test_out_of_band_channels_cannot_rescue_seven_W1_channels():
    import numpy as np

    from discovery.research6_yso_scope import source_scope

    channels = [
        {"wavelength_um": x, "width_um": 0.09, "edge_pixels": 20}
        for x in [3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 2.4, 2.55, 2.7, 4.2, 4.35]
    ]
    visit = {
        "campaign": 0,
        "selected": 12,
        "measured": 12,
        "channels": channels,
        "coverage": {"nominal_support_flat_fnu_photon_fraction": 0.99},
    }
    response = np.array([[3.0, 1.0], [3.6, 1.0]])
    result = source_scope([visit], response)[0]
    assert result["within_scope_nonoverlapping_channels"] == 7
    assert result["within_scope_photon_coverage"] > 0.8
    assert result["spectral_coverage_gate"] is False

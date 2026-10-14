"""Frozen multiplicity and empirical controls cannot be waived for a red patch."""

import numpy as np

from discovery.smacs_e2_photometry import null_gate


def records(value):
    return {
        name: {"status": "measured", "flux_njy": float(value)}
        for name in ("annulus", "poly0", "poly1", "poly2")
    }


def test_small_control_sample_cannot_resolve_frozen_p_cut():
    controls = [[records(x) for x in np.linspace(-1, 1, 40)] for _ in range(2)]
    r = null_gate([records(1000), records(1000)], controls)
    assert all(x["status"] == "failed thresholds" for x in r.values())
    assert r["annulus"]["rank_p"] == 1 / 41


def test_negative_primary_flux_never_passes():
    controls = [[records(x) for x in np.linspace(-1, 1, 100)] for _ in range(2)]
    r = null_gate([records(-1000), records(1000)], controls)
    assert all(x["status"] == "failed thresholds" for x in r.values())


def test_four_operators_keep_frozen_bonferroni_cut():
    controls = [[records(x) for x in np.linspace(-1, 1, 100)] for _ in range(2)]
    r = null_gate([records(1000), records(1000)], controls)
    assert len(r) == 4
    assert all(x["rank_p_threshold"] == 0.0125 for x in r.values())
    assert all(x["status"] == "pass diagnostic thresholds" for x in r.values())


def test_source_excluded_quadratic_background_recovers_signed_flux():
    from astropy.coordinates import SkyCoord
    from astropy.io import fits
    from astropy.wcs import WCS

    from discovery.smacs_e2_photometry import polynomial_aperture
    from tools.jwst.flux_calibration import flux_density_factors

    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [26, 26]
    wcs.wcs.cdelt = [-0.06 / 3600, 0.06 / 3600]
    wcs.wcs.crval = [110.63858928243717, -73.48487214542632]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    yy, xx = np.mgrid[:51, :51]
    c = SkyCoord(*wcs.wcs.crval, unit="deg")
    sky = wcs.pixel_to_world(xx, yy)
    east, north = c.spherical_offsets_to(sky)
    east, north = east.arcsec, north.arcsec
    radius = c.separation(sky).arcsec
    background = 1 + 0.2 * east + 0.4 * north + 0.1 * east**2 - 0.3 * east * north + 0.15 * north**2
    signal = np.where(radius < 0.17, -3.0, 0.0)
    header = wcs.to_header()
    header["BUNIT"] = "MJy/sr"
    bundle = {
        "sci": background + signal,
        "err": np.ones((51, 51)) * 0.1,
        "validity_mask": np.ones((51, 51), dtype=bool),
        "wcs": wcs,
        "header": header,
        "primary_header": fits.Header(),
    }
    r = polynomial_aperture(bundle, c, 2)
    conversion = flux_density_factors(bundle, xx, yy)["factor_jy"]
    expected = float(np.sum(signal * conversion) * 1e9)
    assert r["status"] == "measured"
    assert np.isclose(r["flux_njy"], expected, rtol=1e-8)
    assert r["flux_njy"] < 0

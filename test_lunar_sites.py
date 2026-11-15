"""Offline tests for the lunar site catalogue. These make no network calls."""

from datetime import datetime

import pandas as pd
import pytest

from lunar_analysis import find_visibility_windows
from lunar_ephem import LunarSite, build_horizons_params
from lunar_metrics import compute_site_metrics
from lunar_sites import LUNAR_SITES, CatalogueSite, get_site


def test_every_entry_is_well_formed_and_keyed_by_its_id():
    assert LUNAR_SITES, "catalogue must not be empty"
    for key, site in LUNAR_SITES.items():
        assert key == site.site_id
        assert site.source_url.startswith("https://")
        assert site.source_name.strip()
        assert site.coordinate_system.strip()
        assert site.altitude_basis.strip()


def test_every_entry_is_accepted_by_the_ephemeris_coordinate_checks():
    # Catches a longitude or latitude that the Horizons layer would reject, without
    # making a network request.
    for site in LUNAR_SITES.values():
        LunarSite(site.latitude_deg, site.longitude_deg_east, site.altitude_km)


def test_apollo_11_matches_the_nssdca_lunar_module_row():
    site = get_site("apollo_11_lm")
    assert site.latitude_deg == 0.67416
    assert site.longitude_deg_east == 23.47314
    assert site.altitude_km == 0.0
    assert site.coordinates == (0.67416, 23.47314, 0.0)
    assert site.category == "Historical landing site"
    assert site.status.startswith("Landed")
    assert site.source_url == "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html"


def test_unknown_site_id_gives_a_readable_error():
    with pytest.raises(KeyError, match="apollo_11_lm"):
        get_site("not_a_site")


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"latitude_deg": 91.0},
        {"longitude_deg_east": 200.0},
        {"source_url": "http://example.com"},
        {"source_name": "  "},
        {"site_id": "Has Space"},
    ],
)
def test_invalid_entries_are_rejected(bad_fields):
    valid = dict(
        site_id="test_site",
        name="Test",
        category="Test",
        status="Test",
        latitude_deg=0.0,
        longitude_deg_east=0.0,
        altitude_km=0.0,
        altitude_basis="test",
        coordinate_system="test",
        source_name="test",
        source_url="https://example.com",
        source_updated="test",
    )
    CatalogueSite(**valid)  # the unmodified entry is valid
    with pytest.raises(ValueError):
        CatalogueSite(**{**valid, **bad_fields})


# ---------------------------------------------------------------------------------
# Apollo 11 regression
#
# Real Horizons rows for the Apollo 11 Lunar Module catalogue position, observer on the
# Moon (301), 2026-11-13 00:00-06:00 UTC, 60-minute steps, apparent az/el, no refraction.
# The Sun rows were compared with a manual Horizons web-app run (header: Center body
# Moon (301), centre geodetic 23.47314 E, 0.67416 N, 0 km, centre radii 1737.4 km) and
# matched the script to six decimals. The Earth rows were also checked against the web
# app by hand.
# ---------------------------------------------------------------------------------
APOLLO_11_HORIZONS_RUN = {
    "lon_east_deg": 23.47314,
    "lat_deg": 0.67416,
    "alt_km": 0.0,
}

APOLLO_11_SUN_AZ = [91.402851, 91.403075, 91.403429, 91.403911,
                    91.404520, 91.405254, 91.406113]
APOLLO_11_SUN_EL = [-25.344713, -24.836833, -24.328961, -23.821097,
                    -23.313241, -22.805394, -22.297554]
APOLLO_11_EARTH_AZ = [281.715630, 281.609124, 281.502009, 281.394299,
                      281.286007, 281.177145, 281.067728]
APOLLO_11_EARTH_EL = [66.134402, 66.086710, 66.038840, 65.990793,
                      65.942570, 65.894174, 65.845607]


def test_apollo_11_catalogue_coordinates_are_the_ones_verified_in_horizons():
    site = get_site("apollo_11_lm")
    assert site.longitude_deg_east == APOLLO_11_HORIZONS_RUN["lon_east_deg"]
    assert site.latitude_deg == APOLLO_11_HORIZONS_RUN["lat_deg"]
    assert site.altitude_km == APOLLO_11_HORIZONS_RUN["alt_km"]


def test_apollo_11_builds_the_lunar_observer_request_that_was_verified():
    site = get_site("apollo_11_lm")
    ephem_site = LunarSite(site.latitude_deg, site.longitude_deg_east, site.altitude_km)
    for target_id in (10, 399):
        params = build_horizons_params(
            target_id,
            ephem_site,
            datetime(2026, 11, 13, 0, 0),
            datetime(2026, 11, 13, 6, 0),
            60,
        )
        assert params["COMMAND"] == f"'{target_id}'"
        assert params["CENTER"] == "'coord@301'"  # the Moon, not Earth
        assert params["COORD_TYPE"] == "'GEODETIC'"
        assert params["SITE_COORD"] == "'23.473140,0.674160,0.000000'"  # E-lon, lat, alt km
        assert params["QUANTITIES"] == "'4'"


def test_apollo_11_validated_rows_give_earth_only_visibility():
    n = len(APOLLO_11_SUN_EL)
    data = pd.DataFrame({
        "utc": [pd.Timestamp("2026-11-13 00:00", tz="UTC") + pd.Timedelta(hours=i)
                for i in range(n)],
        "sun_az_deg": APOLLO_11_SUN_AZ,
        "sun_el_deg": APOLLO_11_SUN_EL,
        "earth_az_deg": APOLLO_11_EARTH_AZ,
        "earth_el_deg": APOLLO_11_EARTH_EL,
    })
    m = compute_site_metrics(
        data,
        find_visibility_windows(data, "sun"),
        find_visibility_windows(data, "earth"),
    )
    sun, earth, both = m["sun"], m["earth"], m["both"]

    assert abs(m["period_hours"] - 6.0) < 1e-9

    # Sun below the horizon for the whole period, rising but still negative.
    assert sun["total_hours"] == 0.0 and sun["n_windows"] == 0
    assert abs(sun["longest_gap_hours"] - 6.0) < 1e-9 and sun["longest_gap_truncated"]

    # Earth above the horizon for the whole period.
    assert abs(earth["total_hours"] - 6.0) < 1e-9
    assert abs(earth["fraction_of_period"] - 1.0) < 1e-9
    assert earth["n_windows"] == 1
    assert abs(earth["longest_hours"] - 6.0) < 1e-9 and earth["longest_truncated"]
    assert earth["longest_gap_hours"] == 0.0 and not earth["longest_gap_truncated"]

    assert both["total_hours"] == 0.0
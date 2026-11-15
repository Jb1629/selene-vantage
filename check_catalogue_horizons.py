"""Live check of catalogue sites against JPL Horizons (needs an internet connection).

Usage:
    python check_catalogue_horizons.py              # every catalogue site
    python check_catalogue_horizons.py apollo_12_lm # selected sites only

For each site this asks Horizons for a short Sun/Earth azimuth-elevation table through
the same code path the app uses, then checks that the observer was placed on the Moon
and that the 'Center geodetic' coordinates Horizons echoes back match the catalogue.
The first row is printed so it can also be compared by eye with the Horizons web app.

This is a manual check and is not collected by pytest, so the unit tests never depend
on the network.
"""

import sys

from lunar_ephem import get_sun_earth_azel
from lunar_sites import LUNAR_SITES, get_site

START, END, STEP_MINUTES = "2026-11-13 00:00", "2026-11-13 01:00", 60
DEG_TOL = 5e-5  # Horizons echoes about five decimal places
KM_TOL = 1e-3


def echo_problems(site, verified):
    """Return a list of mismatches between the catalogue and Horizons' echoed coordinates."""
    problems = []
    for target in ("sun", "earth"):
        info = verified[target]
        if info["center_body"] != "Moon (301)":
            problems.append(f"{target}: observer body is {info['center_body']}, not Moon (301)")
        echo = info["center_geodetic"]
        if echo is None:
            problems.append(f"{target}: Horizons did not echo the observer coordinates")
            continue
        lon, lat, alt = echo
        dlon = (lon - site.longitude_deg_east + 180.0) % 360.0 - 180.0  # 336.58 E == -23.42 E
        if abs(dlon) > DEG_TOL or abs(lat - site.latitude_deg) > DEG_TOL \
                or abs(alt - site.altitude_km) > KM_TOL:
            problems.append(
                f"{target}: echoed (E-lon, lat, alt) = {echo}, catalogue has "
                f"({site.longitude_deg_east}, {site.latitude_deg}, {site.altitude_km})"
            )
    return problems


def main(site_ids):
    failures = 0
    for site_id in site_ids:
        site = get_site(site_id)
        df = get_sun_earth_azel(
            site.latitude_deg, site.longitude_deg_east, site.altitude_km,
            START, END, STEP_MINUTES,
        )
        problems = echo_problems(site, df.attrs["verified"])
        first = df.iloc[0]
        print(f"{'FAIL' if problems else 'PASS'}  {site_id}")
        print(f"      catalogue: lat {site.latitude_deg}, E-lon {site.longitude_deg_east}, "
              f"alt {site.altitude_km} km")
        print(f"      {first['utc']}  Sun az/el {first['sun_az_deg']:.6f} / "
              f"{first['sun_el_deg']:.6f}   Earth az/el {first['earth_az_deg']:.6f} / "
              f"{first['earth_el_deg']:.6f}")
        for problem in problems:
            print(f"      PROBLEM: {problem}")
        failures += bool(problems)
    print(f"\n{len(site_ids) - failures} of {len(site_ids)} sites passed the Horizons echo check.")
    return 1 if failures else 0


if __name__ == "__main__":
    ids = sys.argv[1:] or list(LUNAR_SITES)
    sys.exit(main(ids))
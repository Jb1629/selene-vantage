"""Catalogue of documented lunar locations for Selene Vantage.

Purpose
-------
This module only makes the app easier to use: a named site fills in the latitude,
longitude and altitude fields. The ephemeris and analysis code already accepts any
coordinates, so nothing here is required for a calculation and custom coordinates
always remain available in the app.

Coordinate conventions (read before adding a site)
--------------------------------------------------
* Latitude is degrees north and longitude is degrees EAST, the convention used by
  lunar_ephem.py and by the Horizons SITE_COORD input.
* Horizons describes the Moon's figure as a sphere (radii 1737.4 x 1737.4 x 1737.4 km
  in its header), so on that figure geodetic latitude equals planetocentric latitude.
  Planetocentric catalogue values are therefore passed to Horizons unchanged. If a
  future source uses an ellipsoidal or otherwise different latitude definition, record
  that in `coordinate_system` and convert deliberately; never convert silently.
* Altitude is 0 km, meaning on the 1737.4 km reference sphere, unless a source says
  otherwise. Local terrain height is not modelled anywhere in the app.

Rules for entries
-----------------
* Every entry needs a traceable source. Do not add coordinates from memory.
* Say exactly what the point is (lander, rover, instrument, region centre) in `notes`.
* Planned or candidate locations must not be labelled as landed.
"""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class CatalogueSite:
    """One documented lunar location. Longitude is EAST-positive degrees."""

    site_id: str
    name: str
    category: str
    status: str
    latitude_deg: float
    longitude_deg_east: float
    altitude_km: float
    altitude_basis: str
    coordinate_system: str
    source_name: str
    source_url: str
    source_updated: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.site_id or self.site_id != self.site_id.lower() or " " in self.site_id:
            raise ValueError(f"site_id must be lowercase with no spaces, got {self.site_id!r}")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"{self.site_id}: latitude out of range: {self.latitude_deg!r}")
        if not -180.0 <= self.longitude_deg_east <= 180.0:
            raise ValueError(
                f"{self.site_id}: east longitude must be within [-180, 180], "
                f"got {self.longitude_deg_east!r}"
            )
        for field_name in ("name", "category", "status", "altitude_basis", "coordinate_system",
                           "source_name", "source_updated"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{self.site_id}: '{field_name}' must not be empty")
        if not self.source_url.startswith("https://"):
            raise ValueError(f"{self.site_id}: source_url must be an https URL")

    @property
    def coordinates(self) -> Tuple[float, float, float]:
        """(latitude, east longitude, altitude km) in the order the app's fields use."""
        return (self.latitude_deg, self.longitude_deg_east, self.altitude_km)


_NSSDCA_APOLLO_URL = "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html"
_NSSDCA_APOLLO_FRAME = (
    "Planetocentric, Mean Earth/Polar Axis lunar reference system, DE421 ephemeris; "
    "equal to geodetic latitude on Horizons' spherical Moon, so used unchanged"
)
_ZERO_ALTITUDE_BASIS = (
    "Modelling assumption: 0 km on the 1737.4 km reference sphere; "
    "local terrain elevation is not modelled"
)

_NSSDCA_APOLLO_SOURCE = (
    "NASA NSSDCA, Apollo Landing Site Coordinates (Lunar Module row; "
    "from LRO images, Wagner et al., Icarus 283, 92-103, 2017)"
)


_ROVER_NOTE = (
    " The crew also drove a Lunar Roving Vehicle; this entry is the landing point, "
    "not the rover traverse."
)


def _apollo_lunar_module(
    number: int,
    landed: str,
    latitude_deg: float,
    longitude_deg_east: float,
    decimals: int,
    other_points: str,
    rover_note: str = "",
) -> CatalogueSite:
    """Apollo Lunar Module entry from the NSSDCA table, values exactly as published."""
    return CatalogueSite(
        site_id=f"apollo_{number}_lm",
        name=f"Apollo {number} - Lunar Module",
        category="Historical landing site",
        status=f"Landed (crewed, {landed})",
        latitude_deg=latitude_deg,
        longitude_deg_east=longitude_deg_east,
        altitude_km=0.0,
        altitude_basis=_ZERO_ALTITUDE_BASIS,
        coordinate_system=_NSSDCA_APOLLO_FRAME,
        source_name=_NSSDCA_APOLLO_SOURCE,
        source_url=_NSSDCA_APOLLO_URL,
        source_updated="Page last updated 06 March 2017",
        notes=(
            "Position of the Lunar Module descent stage, from the Lunar Module row "
            f"of the NSSDCA table. The same table also lists {other_points}; those are "
            f"not used here. Published to {decimals} decimal places; no uncertainty is "
            "stated on the source page." + rover_note
        ),
    )


_SITES = [
    CatalogueSite(
        site_id="apollo_11_lm",
        name="Apollo 11 - Lunar Module (Tranquility Base)",
        category="Historical landing site",
        status="Landed (crewed, July 1969)",
        latitude_deg=0.67416,
        longitude_deg_east=23.47314,
        altitude_km=0.0,
        altitude_basis=_ZERO_ALTITUDE_BASIS,
        coordinate_system=_NSSDCA_APOLLO_FRAME,
        source_name=(
            "NASA NSSDCA, Apollo Landing Site Coordinates (Lunar Module row; "
            "from LRO images, Wagner et al., Icarus 283, 92-103, 2017)"
        ),
        source_url=_NSSDCA_APOLLO_URL,
        source_updated="Page last updated 06 March 2017",
        notes=(
            "Position of the Lunar Module descent stage, not the retroreflector "
            "(0.67345 N, 23.47307 E on the same page) and not a surface feature. "
            "No uncertainty is stated on the source page. Older and popular values "
            "differ: the earlier NSSDCA table and the Apollo Lunar Surface Journal "
            "differ by about 5 m, while the pre-flight map value used on Wikipedia "
            "(0.6875 N, 23.4333 E) is about 1.3 km away."
        ),
    ),
    _apollo_lunar_module(12, "Nov 1969", -3.0128, -23.4219, 4, "an ALSEP position"),
    _apollo_lunar_module(
        14, "Feb 1971", -3.64589, -17.47194, 5,
        "retroreflector (LRRR) and ALSEP positions",
    ),
    _apollo_lunar_module(
        15, "Jul 1971", 26.13239, 3.63330, 5,
        "retroreflector (LRRR) and ALSEP positions",
        rover_note=_ROVER_NOTE,
    ),
    _apollo_lunar_module(
        16, "Apr 1972", -8.9734, 15.5011, 4, "an ALSEP position",
        rover_note=_ROVER_NOTE,
    ),
    _apollo_lunar_module(
        17, "Dec 1972", 20.1911, 30.7723, 4, "an ALSEP position",
        rover_note=_ROVER_NOTE,
    ),
]

LUNAR_SITES: Dict[str, CatalogueSite] = {site.site_id: site for site in _SITES}

if len(LUNAR_SITES) != len(_SITES):
    raise ValueError("lunar_sites: duplicate site_id in the catalogue")


def get_site(site_id: str) -> CatalogueSite:
    """Return a catalogue entry, with a readable error for an unknown id."""
    try:
        return LUNAR_SITES[site_id]
    except KeyError:
        known = ", ".join(sorted(LUNAR_SITES)) or "(none)"
        raise KeyError(f"Unknown lunar site id {site_id!r}. Known ids: {known}") from None
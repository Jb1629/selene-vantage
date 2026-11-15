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
* A feature-centre coordinate is not a landing ellipse or a surveyed landing point.
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
        for field_name in (
            "name", "category", "status", "altitude_basis", "coordinate_system",
            "source_name", "source_updated",
        ):
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


# The NSSDCA landing table reports north/east-positive coordinates but does not
# explicitly identify a coordinate reference frame for these CLPS rows. Preserve the
# published values and record that limitation rather than assigning the Apollo DE421
# frame to them without evidence.
_NSSDCA_CLPS_URL = (
    "https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html"
)
_NSSDCA_CLPS_FRAME = (
    "NASA NSSDCA published N/E-positive latitude and longitude; the landing table does "
    "not explicitly state the coordinate reference frame. Values are retained unchanged "
    "for the spherical Horizons lunar observer; no frame transformation is claimed."
)

# The USGS/IAU Gazetteer explicitly gives feature-centre coordinates as planetographic,
# +East, with longitude in [-180, 180]. On Horizons' spherical lunar figure, the
# planetographic and planetocentric latitudes coincide.
_USGS_PLANETOGRAPHIC_FRAME = (
    "USGS/IAU Gazetteer, planetographic latitude, east-positive longitude in [-180, 180]; "
    "used unchanged because Horizons models the lunar reference figure as a sphere"
)


def _clps_landed(
    site_id: str,
    name: str,
    status: str,
    latitude_deg: float,
    longitude_deg_east: float,
    lroc_url: str,
    notes: str,
) -> CatalogueSite:
    """A completed CLPS landing using the published NSSDCA/LROC lander position."""
    return CatalogueSite(
        site_id=site_id,
        name=name,
        category="Historical CLPS landing site",
        status=status,
        latitude_deg=latitude_deg,
        longitude_deg_east=longitude_deg_east,
        altitude_km=0.0,
        altitude_basis=_ZERO_ALTITUDE_BASIS,
        coordinate_system=_NSSDCA_CLPS_FRAME,
        source_name=(
            "NASA NSSDCA, Table of Anthropogenic Impacts and Spacecraft on the Moon "
            "(Lander row); corroborating NASA/ASU Lunar Reconnaissance Orbiter Camera "
            "(LROC) landing-site image"
        ),
        source_url=_NSSDCA_CLPS_URL,
        source_updated="NSSDCA and LROC pages accessed 15 November 2026",
        notes=(
            notes + " The NSSDCA landing table does not explicitly state the coordinate "
            "reference frame. Altitude is retained at 0 km on the Horizons reference "
            "sphere; published local topographic elevation is not imported. LROC source: "
            + lroc_url
        ),
    )


def _clps_target_region(
    site_id: str,
    name: str,
    status: str,
    latitude_deg: float,
    longitude_deg_east: float,
    feature_id: int,
    usgs_updated: str,
    nasa_mission_source: str,
    nasa_mission_url: str,
    notes: str,
) -> CatalogueSite:
    """A planned CLPS destination represented by its IAU/USGS feature centre."""
    usgs_url = f"https://planetarynames.wr.usgs.gov/Feature/{feature_id}"
    return CatalogueSite(
        site_id=site_id,
        name=name,
        category="Planned CLPS destination region",
        status=status,
        latitude_deg=latitude_deg,
        longitude_deg_east=longitude_deg_east,
        altitude_km=0.0,
        altitude_basis=_ZERO_ALTITUDE_BASIS,
        coordinate_system=_USGS_PLANETOGRAPHIC_FRAME,
        source_name=(
            f"USGS/IAU Gazetteer of Planetary Nomenclature, Moon feature ID {feature_id} "
            f"(feature centre); {nasa_mission_source}"
        ),
        source_url=usgs_url,
        source_updated=f"USGS feature page last updated {usgs_updated}; mission page accessed 15 November 2026",
        notes=(
            "Representative feature centre of the named lunar feature, not a precise lander "
            "coordinate, landing ellipse, or surveyed touchdown point. "
            + notes
            + " Mission source: "
            + nasa_mission_url
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

    # Completed CLPS landings. Coordinates are the published lander positions, not
    # nearby craters, instruments, or a mission's wider target region.
    _clps_landed(
        site_id="clps_im1_odysseus",
        name="IM-1 - Odysseus (Malapert A)",
        status="Landed (uncrewed, 22 February 2024; came to rest tilted)",
        latitude_deg=-80.13,
        longitude_deg_east=1.44,
        lroc_url="https://www.lroc.asu.edu/posts/1360",
        notes=(
            "Actual Odysseus lander position. LROC reports 80.13 degrees south, "
            "1.44 degrees east, within a degraded crater with locally sloping terrain."
        ),
    ),
    _clps_landed(
        site_id="clps_im2_athena",
        name="IM-2 - Athena (near Mons Mouton centre)",
        status="Landed (uncrewed, 6 March 2025; came to rest on its side)",
        latitude_deg=-84.7906,
        longitude_deg_east=29.1957,
        lroc_url="https://www.lroc.asu.edu/images/1408",
        notes=(
            "Actual Athena lander position, inside a small crater near the centre of "
            "Mons Mouton. It is not the centre coordinate of Mons Mouton itself. "
            "NASA also lists Mons Mouton as the destination for the planned IM-4 mission."
        ),
    ),
    _clps_landed(
        site_id="clps_blue_ghost_1",
        name="Blue Ghost Mission 1 (Mare Crisium)",
        status="Landed (uncrewed, 2 March 2025; successful landing)",
        latitude_deg=18.562,
        longitude_deg_east=61.810,
        lroc_url="https://www.lroc.asu.edu/images/1406",
        notes=(
            "Actual Blue Ghost lander position in Mare Crisium, about 4 km from the "
            "centre of Mons Latreille. This is the lander position, not the volcanic "
            "cone's centre."
        ),
    ),

    # Planned CLPS mission destinations. Each uses the USGS/IAU named-feature centre
    # only as a representative map point; none is an asserted landing coordinate.
    _clps_target_region(
        site_id="clps_griffin1_nobile_centre",
        name="Nobile Crater - Griffin-1 destination region centre",
        status="Planned (Voyager Griffin-1; NASA schedule: late 2026)",
        latitude_deg=-85.28,
        longitude_deg_east=53.27,
        feature_id=4321,
        usgs_updated="18 October 2010",
        nasa_mission_source="NASA Moon Base: Voyager Griffin-1 (Nobile Crater destination; late 2026)",
        nasa_mission_url="https://www.nasa.gov/event/clps-flight-astrobotics-griffin-mission-one/",
        notes=(
            "Nobile is a named crater near the lunar south pole. NASA identifies the "
            "crater as Griffin-1's destination; this catalogue point is the USGS crater "
            "centre, not the lander's final touchdown coordinate."
        ),
    ),
    _clps_target_region(
        site_id="clps_im3_reiner_gamma_centre",
        name="Reiner Gamma - IM-3 destination region centre",
        status="Planned (Intuitive Machines IM-3; NASA schedule: early 2027)",
        latitude_deg=7.39,
        longitude_deg_east=-58.96,
        feature_id=4987,
        usgs_updated="18 October 2010",
        nasa_mission_source=(
            "NASA CLPS Providers (Reiner Gamma destination) and NASA Moon Base: "
            "Intuitive Machines IM-3 (early 2027 schedule)"
        ),
        nasa_mission_url="https://www.nasa.gov/event/clps-flight-intuitive-machines-im-3/",
        notes=(
            "Reiner Gamma is an adopted IAU albedo feature, not a crater. The point is "
            "the Gazetteer's feature centre and is supplied only as a representative "
            "reference for the broad IM-3 destination region."
        ),
    ),
    _clps_target_region(
        site_id="clps_im4_mons_mouton_centre",
        name="Mons Mouton - IM-4 destination region centre",
        status="Planned (Intuitive Machines IM-4; NASA schedule: 2027)",
        latitude_deg=-84.60,
        longitude_deg_east=31.00,
        feature_id=16070,
        usgs_updated="13 May 2022",
        nasa_mission_source="NASA Moon Base: Intuitive Machines IM-4 (Mons Mouton destination; 2027)",
        nasa_mission_url="https://www.nasa.gov/event/clps-flight-intuitive-machines-im-4-2/",
        notes=(
            "Mons Mouton is a named 130 km lunar mountain feature near the south pole. "
            "The IM-2 Athena lander is catalogued separately at its actual touchdown "
            "position nearby; this entry is the named feature centre used as a planning "
            "reference for IM-4, not a second known landing point."
        ),
    ),
    _clps_target_region(
        site_id="clps_blue_ghost2_nassau_centre",
        name="Nassau Crater - Blue Ghost Mission 2 destination region centre",
        status="Planned (Firefly Blue Ghost Mission 2; no earlier than 2027)",
        latitude_deg=-24.91,
        longitude_deg_east=177.34,
        feature_id=4159,
        usgs_updated="18 October 2010",
        nasa_mission_source="Firefly Aerospace, Blue Ghost Mission 2 (landing near Nassau Crater; no earlier than 2027)",
        nasa_mission_url="https://fireflyspace.com/missions/blue-ghost-mission-2/",
        notes=(
            "Nassau is a named crater on the lunar far side. Firefly describes the "
            "landing site as near Nassau Crater; this entry uses the USGS crater centre "
            "as a representative point, not a defined landing ellipse or touchdown point."
        ),
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

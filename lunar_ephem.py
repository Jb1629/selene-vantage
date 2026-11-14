"""
lunar_ephem.py - Stage 1: Sun and Earth azimuth/elevation seen from a lunar-surface
observer, via the JPL Horizons API.

Conventions
-----------
* Observer: a point on the Moon (Horizons body 301) given as latitude (deg, north +),
  EAST longitude (deg, east +) and altitude (km above Horizons' lunar reference surface).
  Every request names the Moon as the central body ("coord@301"), and every response
  header is checked before any data is returned (see verify_observer_header). If Horizons
  ever placed the observer on another body - the mistake made in the manual test, where
  Earth was the coordinate body - an ObserverMismatchError is raised instead of data.
* Targets: Sun (10) and Earth (399, the geocentre).
* Quantity: Horizons observer quantity 4, apparent azimuth/elevation (airless on the Moon).
  Azimuth: degrees east of local north, 0-360. Elevation: degrees above the local
  horizontal plane (a mathematical horizon: no terrain).
* Time: UT/UTC throughout. Naive datetimes passed in are treated as UTC.

Public entry point
------------------
get_sun_earth_azel(lat_deg, lon_deg, alt_km, start, end, step_minutes) -> pandas.DataFrame
    columns: utc, sun_az_deg, sun_el_deg, earth_az_deg, earth_el_deg
    df.attrs["headers"] keeps the Horizons header text of both requests as the record of
    exactly which observer was used.
"""
from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, NamedTuple, Optional, Tuple, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

__all__ = [
    "HORIZONS_API_URL",
    "SUN_ID",
    "EARTH_ID",
    "MOON_ID",
    "HorizonsError",
    "ObserverMismatchError",
    "LunarSite",
    "AzElSeries",
    "angle_diff_deg",
    "build_horizons_params",
    "make_session",
    "parse_ephemeris_text",
    "verify_observer_header",
    "fetch_azel",
    "get_sun_earth_azel",
]

HORIZONS_API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

SUN_ID = 10
EARTH_ID = 399
MOON_ID = 301

DEFAULT_TIMEOUT_S = 60.0
USER_AGENT = "lunar-site-browser/0.1 (NASA Space Apps 2026)"

# The header echo check is deliberately coarse: it exists to catch the wrong body or
# swapped/mangled coordinates, not to audit the last decimal place.
GEODETIC_ECHO_TOL_DEG = 1e-2
GEODETIC_ECHO_TOL_KM = 1e-2

TimeLike = Union[str, date, datetime, pd.Timestamp]


class HorizonsError(RuntimeError):
    """Horizons returned an error, or a response this module could not interpret."""


class ObserverMismatchError(HorizonsError):
    """The Horizons header does not describe the observer/target that was asked for."""


@dataclass(frozen=True)
class LunarSite:
    """A point on the lunar surface. Longitude is EAST-positive degrees."""

    lat_deg: float
    lon_deg: float
    alt_km: float = 0.0
    name: str = ""

    def __post_init__(self) -> None:
        if not -90.0 <= float(self.lat_deg) <= 90.0:
            raise ValueError(f"latitude must be within [-90, 90] degrees, got {self.lat_deg!r}")
        if not -360.0 <= float(self.lon_deg) <= 360.0:
            raise ValueError(
                f"east longitude must be within [-360, 360] degrees, got {self.lon_deg!r}"
            )
        if not math.isfinite(float(self.alt_km)):
            raise ValueError(f"altitude must be a finite number of km, got {self.alt_km!r}")


class AzElSeries(NamedTuple):
    """One Horizons observer table plus the evidence of how it was produced."""

    data: pd.DataFrame  # columns: utc (tz-aware), az_deg, el_deg
    header: str  # Horizons header block (kept as confirmation of the observer set-up)
    raw: str  # the complete raw Horizons result text
    verified: Dict[str, Any]  # what verify_observer_header confirmed
    api_version: Optional[str]  # Horizons API "signature" version


def angle_diff_deg(a, b):
    """Signed smallest difference a - b in degrees, in [-180, 180). Works on arrays too.

    Use for azimuth comparisons: 359.96 vs 0.12 differ by -0.16 deg, not 359.84.
    """
    return (a - b + 180.0) % 360.0 - 180.0


# --------------------------------------------------------------------------------------
# Request construction
# --------------------------------------------------------------------------------------
def _as_utc_naive_minute(value: TimeLike, label: str) -> datetime:
    """Normalise user input to a naive UTC datetime on a whole minute."""
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Could not interpret {label} time {value!r}") from exc
    if pd.isna(ts):
        raise ValueError(f"Could not interpret {label} time {value!r}")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    if ts.second or ts.microsecond or ts.nanosecond:
        raise ValueError(f"{label} time must fall on a whole minute, got {ts}")
    return ts.to_pydatetime()


def _validate_step(step_minutes: Any) -> int:
    if isinstance(step_minutes, bool) or not isinstance(step_minutes, (int, float)):
        raise ValueError(f"step_minutes must be a whole number >= 1, got {step_minutes!r}")
    if step_minutes < 1 or int(step_minutes) != step_minutes:
        raise ValueError(f"step_minutes must be a whole number >= 1, got {step_minutes!r}")
    return int(step_minutes)


def build_horizons_params(
    target_id: int,
    site: LunarSite,
    start_utc: datetime,
    stop_utc: datetime,
    step_minutes: int,
) -> Dict[str, str]:
    """Query parameters for one Horizons observer table (parameter names per the API docs).

    The observer is always a user-defined point on body 301 (the Moon):
    CENTER='coord@301' with SITE_COORD = 'east-longitude, latitude, altitude-km'.
    """
    return {
        "format": "json",
        "COMMAND": f"'{int(target_id)}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": f"'coord@{MOON_ID}'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site.lon_deg:.6f},{site.lat_deg:.6f},{site.alt_km:.6f}'",
        "START_TIME": f"'{start_utc:%Y-%m-%d %H:%M}'",
        "STOP_TIME": f"'{stop_utc:%Y-%m-%d %H:%M}'",
        "STEP_SIZE": f"'{int(step_minutes)}m'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'4'",
        "CSV_FORMAT": "'YES'",
    }


def make_session() -> requests.Session:
    """A requests session that retries transient Horizons failures (HTTP 5xx) a few times."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = USER_AGENT
    return session


def _error_text(resp: Any) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and body.get("message"):
            return str(body["message"])
    except ValueError:
        pass
    return str(getattr(resp, "text", ""))[:300]


def _query_horizons(params: Dict[str, str], session: Any, timeout: float) -> Dict[str, Any]:
    try:
        resp = session.get(HORIZONS_API_URL, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise HorizonsError(f"Could not reach JPL Horizons ({type(exc).__name__}: {exc})") from exc
    url = getattr(resp, "url", HORIZONS_API_URL)
    if resp.status_code != 200:
        raise HorizonsError(
            f"Horizons returned HTTP {resp.status_code}: {_error_text(resp)}\nRequest: {url}"
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise HorizonsError(f"Horizons returned non-JSON content: {resp.text[:300]!r}") from exc
    if not isinstance(payload, dict):
        raise HorizonsError(f"Unexpected Horizons payload: {str(payload)[:300]}")
    if payload.get("error"):
        raise HorizonsError(f"Horizons reported an error: {payload['error']}\nRequest: {url}")
    if "result" not in payload:
        raise HorizonsError(f"Horizons response had no 'result' field: {str(payload)[:300]}")
    return payload


# --------------------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------------------
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}
_TIME_RE = re.compile(
    r"^\s*(?P<y>\d{4})-(?P<mon>[A-Za-z]{3})-(?P<d>\d{2})\s+(?P<H>\d{2}):(?P<M>\d{2})"
    r"(?::(?P<S>\d{2}))?"
)
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_CENTER_BODY_RE = re.compile(
    r"^\s*Center body name\s*:\s*(?P<name>.*?)\s*\((?P<id>-?\d+)\)", re.MULTILINE
)
_TARGET_BODY_RE = re.compile(
    r"^\s*Target body name\s*:\s*(?P<name>.*?)\s*\((?P<id>-?\d+)\)", re.MULTILINE
)
_CENTER_GEODETIC_RE = re.compile(
    rf"^\s*Center geodetic\s*:\s*(?P<lon>{_NUM})\s*,\s*(?P<lat>{_NUM})\s*,\s*(?P<alt>{_NUM})",
    re.MULTILINE,
)


def _parse_horizons_time(text: str) -> datetime:
    """Parse '2026-Nov-13 00:00' without depending on the machine's locale."""
    from datetime import timezone

    m = _TIME_RE.match(text)
    if m is None or m["mon"].title() not in _MONTHS:
        raise HorizonsError(f"Unrecognised Horizons time stamp: {text!r}")
    return datetime(
        int(m["y"]),
        _MONTHS[m["mon"].title()],
        int(m["d"]),
        int(m["H"]),
        int(m["M"]),
        int(m["S"] or 0),
        tzinfo=timezone.utc,
    )


def _index_of(lines, marker: str, start: int) -> Optional[int]:
    for i in range(start, len(lines)):
        if lines[i].strip() == marker:
            return i
    return None


def parse_ephemeris_text(text: str) -> Tuple[str, pd.DataFrame]:
    """Split a Horizons observer-table result into (header_text, DataFrame).

    The azimuth/elevation columns are located by NAME in the column-header line, not by
    position, so extra flag columns cannot silently shift the data.
    DataFrame columns: utc (tz-aware), az_deg, el_deg.
    """
    lines = text.splitlines()
    soe = _index_of(lines, "$$SOE", 0)
    if soe is None:
        raise HorizonsError(
            "No ephemeris table ($$SOE) in the Horizons response. Start of response:\n"
            + "\n".join(lines[:20])
        )
    eoe = _index_of(lines, "$$EOE", soe + 1)
    if eoe is None:
        raise HorizonsError("Ephemeris table was not terminated ($$EOE) - response incomplete.")

    header = "\n".join(lines[:soe]).strip("\n")
    col_line = next(
        (
            ln
            for ln in reversed(lines[:soe])
            if re.search(r"azi", ln, re.I) and re.search(r"elev", ln, re.I)
        ),
        None,
    )
    if col_line is None:
        raise HorizonsError(
            "Could not find the azimuth/elevation column header above $$SOE. Header tail:\n"
            + "\n".join(lines[max(0, soe - 6) : soe])
        )
    cols = [c.strip().lower() for c in col_line.split(",")]
    try:
        i_az = next(i for i, c in enumerate(cols) if c.startswith("azi"))
        i_el = next(i for i, c in enumerate(cols) if c.startswith("elev"))
    except StopIteration:
        raise HorizonsError(f"Unexpected column header (is CSV output on?): {col_line!r}")

    rows = []
    for ln in lines[soe + 1 : eoe]:
        if not ln.strip():
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) <= max(i_az, i_el):
            raise HorizonsError(f"Unexpected table row (too few columns): {ln!r}")
        try:
            rows.append((_parse_horizons_time(parts[0]), float(parts[i_az]), float(parts[i_el])))
        except ValueError as exc:
            raise HorizonsError(f"Could not parse table row {ln!r}") from exc
    if not rows:
        raise HorizonsError("Ephemeris table is empty.")

    df = pd.DataFrame(rows, columns=["utc", "az_deg", "el_deg"])
    df["utc"] = pd.to_datetime(df["utc"], utc=True)
    if not df["az_deg"].between(0.0, 360.0).all() or not df["el_deg"].between(-90.0, 90.0).all():
        raise HorizonsError("Azimuth/elevation outside the expected ranges - refusing to use data.")
    return header, df


def _header_excerpt(header: str) -> str:
    keys = ("Target body name", "Center body name", "Center-site name", "Center geodetic")
    keep = [ln.strip() for ln in header.splitlines() if ln.strip().startswith(keys)]
    return "\n".join(keep) if keep else header[:500]


def verify_observer_header(header: str, target_id: int, site: LunarSite) -> Dict[str, Any]:
    """Confirm the Horizons header describes a lunar observer at the requested coordinates.

    Raises ObserverMismatchError if:
      * the central body is not the Moon (301), or cannot be found (fails closed);
      * the target is not the requested one;
      * the 'Center geodetic' echo (E-lon, lat, alt-km) disagrees with the request.
    A missing 'Center geodetic' line only warns, because the data are still bound to the
    confirmed central body. Returns a small dict recording what was confirmed.
    """
    center = _CENTER_BODY_RE.search(header)
    if center is None:
        raise ObserverMismatchError(
            "Could not find 'Center body name' in the Horizons header, so the observer's "
            "central body could not be confirmed. Refusing to use this data.\n"
            + _header_excerpt(header)
        )
    if int(center["id"]) != MOON_ID:
        raise ObserverMismatchError(
            f"Horizons placed the observer on {center['name']} ({center['id']}), not the Moon "
            f"({MOON_ID}): the coordinates were interpreted as a location on the wrong body.\n"
            + _header_excerpt(header)
        )

    target = _TARGET_BODY_RE.search(header)
    if target is None or int(target["id"]) != int(target_id):
        found = f"{target['name']} ({target['id']})" if target else "no target line"
        raise ObserverMismatchError(
            f"Expected Horizons target id {target_id} but the header reports {found}.\n"
            + _header_excerpt(header)
        )

    info: Dict[str, Any] = {
        "center_body": f"{center['name']} ({center['id']})",
        "target_body": f"{target['name']} ({target['id']})",
        "center_geodetic": None,
    }

    geo = _CENTER_GEODETIC_RE.search(header)
    if geo is None:
        warnings.warn(
            "Horizons header has no 'Center geodetic' line; the observer coordinates were "
            "not echo-checked (central body was confirmed as the Moon).",
            RuntimeWarning,
            stacklevel=3,
        )
        return info

    lon, lat, alt = float(geo["lon"]), float(geo["lat"]), float(geo["alt"])
    dlon = (lon - site.lon_deg + 180.0) % 360.0 - 180.0  # tolerate 350 E vs -10 E
    if (
        abs(dlon) > GEODETIC_ECHO_TOL_DEG
        or abs(lat - site.lat_deg) > GEODETIC_ECHO_TOL_DEG
        or abs(alt - site.alt_km) > GEODETIC_ECHO_TOL_KM
    ):
        raise ObserverMismatchError(
            "Horizons echoed different observer coordinates than requested.\n"
            f"  requested (E-lon, lat, alt-km): {site.lon_deg}, {site.lat_deg}, {site.alt_km}\n"
            f"  header    (E-lon, lat, alt-km): {lon}, {lat}, {alt}\n" + _header_excerpt(header)
        )
    info["center_geodetic"] = (lon, lat, alt)
    return info


# --------------------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------------------
def fetch_azel(
    target_id: int,
    site: LunarSite,
    start: TimeLike,
    end: TimeLike,
    step_minutes: int = 60,
    *,
    session: Any = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> AzElSeries:
    """Azimuth/elevation of one target (Sun 10, Earth 399) from a lunar-surface site.

    `end` is inclusive when it falls on the step grid. Raises ObserverMismatchError if the
    header does not confirm a lunar observer, and HorizonsError for any other problem
    (HTTP error, Horizons error text, missing/short/irregular table).
    """
    step = _validate_step(step_minutes)
    start_dt = _as_utc_naive_minute(start, "start")
    end_dt = _as_utc_naive_minute(end, "end")
    if end_dt <= start_dt:
        raise ValueError(f"end ({end_dt}) must be after start ({start_dt})")

    params = build_horizons_params(target_id, site, start_dt, end_dt, step)
    payload = _query_horizons(params, session if session is not None else make_session(), timeout)

    api_version = (payload.get("signature") or {}).get("version")
    if api_version is not None and not str(api_version).startswith("1."):
        warnings.warn(
            f"Horizons API version is {api_version!r}; this code was written for 1.x and the "
            "output format may have changed.",
            RuntimeWarning,
            stacklevel=2,
        )

    raw = payload["result"]
    header, df = parse_ephemeris_text(raw)
    verified = verify_observer_header(header, target_id, site)

    expected_rows = int((end_dt - start_dt) // timedelta(minutes=step)) + 1
    if len(df) != expected_rows:
        raise HorizonsError(
            f"Expected {expected_rows} rows for {start_dt} -> {end_dt} every {step} min, "
            f"Horizons returned {len(df)}."
        )
    if df["utc"].iloc[0] != pd.Timestamp(start_dt, tz="UTC"):
        raise HorizonsError(
            f"First time stamp {df['utc'].iloc[0]} does not match requested start {start_dt} UTC."
        )
    if (df["utc"].diff().dropna() != pd.Timedelta(minutes=step)).any():
        raise HorizonsError(f"Row spacing is not the requested {step} minutes.")

    return AzElSeries(df, header, raw, verified, api_version)


def get_sun_earth_azel(
    lat_deg: float,
    lon_deg: float,
    alt_km: float,
    start: TimeLike,
    end: TimeLike,
    step_minutes: int = 60,
    *,
    session: Any = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> pd.DataFrame:
    """Sun and Earth azimuth/elevation for a lunar-surface observer on one UTC timeline.

    lon_deg is EAST-positive. Makes two Horizons requests (Sun, then Earth), one after the
    other, and merges them on identical time stamps.

    Returns a DataFrame with columns
        utc (tz-aware), sun_az_deg, sun_el_deg, earth_az_deg, earth_el_deg
    and metadata in df.attrs ("observer", "step_minutes", "api_version", "headers",
    "verified"). Elevation > 0 means above the geometric horizon.
    """
    site = LunarSite(lat_deg, lon_deg, alt_km)
    sess = session if session is not None else make_session()
    sun = fetch_azel(SUN_ID, site, start, end, step_minutes, session=sess, timeout=timeout)
    earth = fetch_azel(EARTH_ID, site, start, end, step_minutes, session=sess, timeout=timeout)
    if not sun.data["utc"].equals(earth.data["utc"]):
        raise HorizonsError("Sun and Earth tables have different time stamps; cannot merge.")

    out = pd.DataFrame(
        {
            "utc": sun.data["utc"],
            "sun_az_deg": sun.data["az_deg"],
            "sun_el_deg": sun.data["el_deg"],
            "earth_az_deg": earth.data["az_deg"],
            "earth_el_deg": earth.data["el_deg"],
        }
    )
    out.attrs.update(
        {
            "source": "JPL Horizons API, observer table, quantity 4 (apparent az/el)",
            "api_version": sun.api_version,
            "observer": {
                "body": "Moon (301)",
                "lat_deg": site.lat_deg,
                "lon_deg_east": site.lon_deg,
                "alt_km": site.alt_km,
            },
            "step_minutes": int(step_minutes),
            "headers": {"sun": sun.header, "earth": earth.header},
            "verified": {"sun": sun.verified, "earth": earth.verified},
        }
    )
    return out

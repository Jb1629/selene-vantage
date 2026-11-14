import math
import pandas as pd

from lunar_ephem import get_sun_earth_azel
from lunar_metrics import compute_site_metrics

# ---------------------------------------------------------
# STAGE 2: LUNAR VISIBILITY ANALYSIS
# ---------------------------------------------------------

def add_visibility_flags(
    df: pd.DataFrame,
    horizon_deg: float = 0.0,
) -> pd.DataFrame:
    """
    Add Boolean columns identifying whether the Sun and Earth
    are geometrically above the lunar horizon.

    Elevation strictly greater than horizon_deg = visible.
    Returns a copy; the original DataFrame is not modified.
    """

    required = ["utc", "sun_el_deg", "earth_el_deg"]

    for column in required:
        if column not in df.columns:
            raise ValueError(f"Missing required column: {column}")

    horizon_deg = float(horizon_deg)

    if not math.isfinite(horizon_deg) or not -90 <= horizon_deg <= 90:
        raise ValueError("horizon_deg must be between -90 and 90.")

    result = df.copy()

    result["utc"] = pd.to_datetime(result["utc"], utc=True)

    result["sun_visible"] = (
        pd.to_numeric(result["sun_el_deg"], errors="raise") > horizon_deg
    )

    result["earth_visible"] = (
        pd.to_numeric(result["earth_el_deg"], errors="raise") > horizon_deg
    )

    return result


def find_visibility_windows(
    df: pd.DataFrame,
    target: str = "sun",
    horizon_deg: float = 0.0,
) -> pd.DataFrame:
    """
    Identify periods when the selected target is above the
    geometric lunar horizon.

    target must be either 'sun' or 'earth'.

    Horizon-crossing times are estimated through linear
    interpolation between adjacent observations.

    Windows already in progress at the beginning or end
    of the requested time range are marked accordingly.
    """

    target = target.strip().lower()

    elevation_columns = {
        "sun": "sun_el_deg",
        "earth": "earth_el_deg",
    }

    if target not in elevation_columns:
        raise ValueError("target must be either 'sun' or 'earth'.")

    elevation_column = elevation_columns[target]

    if "utc" not in df.columns or elevation_column not in df.columns:
        raise ValueError(
            f"DataFrame must contain 'utc' and '{elevation_column}'."
        )

    horizon_deg = float(horizon_deg)

    if not math.isfinite(horizon_deg) or not -90 <= horizon_deg <= 90:
        raise ValueError("horizon_deg must be between -90 and 90.")

    times = pd.to_datetime(df["utc"], utc=True, errors="raise")
    elevations = pd.to_numeric(
        df[elevation_column], errors="raise"
    ).astype(float)

    if times.isna().any() or elevations.isna().any():
        raise ValueError("Time and elevation data cannot contain missing values.")

    if len(df) < 2:
        raise ValueError("At least two observations are required.")

    if not times.is_monotonic_increasing or times.duplicated().any():
        raise ValueError("Observations must have unique, increasing timestamps.")

    if not all(math.isfinite(value) for value in elevations):
        raise ValueError("Elevation data must contain finite numbers.")

    time_values = list(times)
    elevation_values = elevations.tolist()

    visible = [
        elevation > horizon_deg
        for elevation in elevation_values
    ]

    windows = []

    active_start = None
    start_event = None

    # Handle a target already visible at the beginning.
    if visible[0]:
        active_start = time_values[0]
        start_event = "already_visible_at_start"

    # Examine each pair of adjacent observations.
    for i in range(1, len(time_values)):

        previous_visible = visible[i - 1]
        current_visible = visible[i]

        if previous_visible == current_visible:
            continue

        t0 = time_values[i - 1]
        t1 = time_values[i]

        e0 = elevation_values[i - 1]
        e1 = elevation_values[i]

        # Estimate the horizon crossing through interpolation.
        fraction = (horizon_deg - e0) / (e1 - e0)

        fraction = max(0.0, min(1.0, fraction))

        crossing_time = t0 + (t1 - t0) * fraction

        # Below -> above: target rises.
        if not previous_visible and current_visible:
            active_start = crossing_time
            start_event = "rise"

        # Above -> below: target sets.
        elif previous_visible and not current_visible:

            if active_start is not None:

                duration_hours = (
                    crossing_time - active_start
                ).total_seconds() / 3600.0

                windows.append({
                    "target": target,
                    "start_utc": active_start,
                    "end_utc": crossing_time,
                    "duration_hours": duration_hours,
                    "start_event": start_event,
                    "end_event": "set",
                })

            active_start = None
            start_event = None

    # Handle a target still visible at the end of the data.
    if active_start is not None:

        end_time = time_values[-1]

        duration_hours = (
            end_time - active_start
        ).total_seconds() / 3600.0

        windows.append({
            "target": target,
            "start_utc": active_start,
            "end_utc": end_time,
            "duration_hours": duration_hours,
            "start_event": start_event,
            "end_event": "still_visible_at_end",
        })

    columns = [
        "target",
        "start_utc",
        "end_utc",
        "duration_hours",
        "start_event",
        "end_event",
    ]

    return pd.DataFrame(windows, columns=columns)


def analyse_lunar_site(
    lat_deg: float,
    lon_deg: float,
    alt_km: float,
    start: str,
    end: str,
    step_minutes: int = 60,
    horizon_deg: float = 0.0,
) -> dict:
    """
    Complete Stage 2 analysis for one lunar location.

    1. Retrieves Sun and Earth ephemeris data.
    2. Adds visibility flags.
    3. Identifies visibility windows.
    4. Calculates basic visibility statistics.

    Returns a dictionary containing:
        data     - observations and visibility flags
        windows  - Sun and Earth visibility windows
        summary  - site information and sample statistics
    """

    # Retrieve verified Stage 1 ephemeris data.
    raw_data = get_sun_earth_azel(
        lat_deg=lat_deg,
        lon_deg=lon_deg,
        alt_km=alt_km,
        start=start,
        end=end,
        step_minutes=step_minutes,
    )

    # Add visibility classifications.
    data = add_visibility_flags(
        raw_data,
        horizon_deg=horizon_deg,
    )

    # Calculate visibility windows.
    sun_windows = find_visibility_windows(
        data,
        target="sun",
        horizon_deg=horizon_deg,
    )

    earth_windows = find_visibility_windows(
        data,
        target="earth",
        horizon_deg=horizon_deg,
    )

    # Basic statistics.
    total_samples = len(data)

    sun_visible_samples = int(data["sun_visible"].sum())
    earth_visible_samples = int(data["earth_visible"].sum())

    summary = {
        "observer": raw_data.attrs.get("observer", {
            "body": "Moon (301)",
            "lat_deg": lat_deg,
            "lon_deg_east": lon_deg,
            "alt_km": alt_km,
        }),
        "start_utc": data["utc"].iloc[0],
        "end_utc": data["utc"].iloc[-1],
        "step_minutes": step_minutes,
        "horizon_deg": horizon_deg,
        "total_samples": total_samples,
        "sun_visible_samples": sun_visible_samples,
        "earth_visible_samples": earth_visible_samples,
        "sun_visible_sample_fraction": (
            sun_visible_samples / total_samples
        ),
        "earth_visible_sample_fraction": (
            earth_visible_samples / total_samples
        ),
    }

    return {
        "data": data,
        "windows": {
            "sun": sun_windows,
            "earth": earth_windows,
        },
        "summary": summary,
        "metrics": compute_site_metrics(data, sun_windows, earth_windows),
    }

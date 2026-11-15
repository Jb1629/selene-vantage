from datetime import date, datetime, time, timedelta

import plotly.graph_objects as go
import streamlit as st

from lunar_analysis import analyse_lunar_site
from lunar_metrics import compare_sites, metrics_table
from lunar_sites import LUNAR_SITES


st.set_page_config(
    page_title="Selene Vantage",
    page_icon="🌕",
    layout="wide",
)


@st.cache_data(show_spinner=False, ttl=3600)
def run_analysis(lat, lon, alt, start, end, step_minutes):
    """Cached wrapper so repeat clicks and repeat visitors do not re-query JPL Horizons."""
    return analyse_lunar_site(
        lat_deg=lat,
        lon_deg=lon,
        alt_km=alt,
        start=start,
        end=end,
        step_minutes=step_minutes,
        horizon_deg=0.0,
    )


st.title("🌕 Selene Vantage")
st.write(
    "Compare solar illumination and direct Earth visibility "
    "at two locations on the lunar surface."
)

st.caption("Ephemeris source: NASA/JPL Horizons | Times in UTC")

# ---------------------------------------------------------
# SIDEBAR: OBSERVER LOCATIONS
# ---------------------------------------------------------

CUSTOM_SITE = "custom"


def site_label(choice):
    """Display name for a dropdown value or a stored choice."""
    return "Custom coordinates" if choice == CUSTOM_SITE else LUNAR_SITES[choice].name


def location_inputs(prefix, title, default_lat, default_lon, default_alt):
    """Sidebar controls for one site; returns (choice, lat, lon_east, alt_km).

    A catalogue site fills in the coordinates and locks them, so the numbers shown
    can never disagree with the named site. Choose "Custom coordinates" to type
    any latitude, east longitude and altitude.
    """
    st.sidebar.header(title)

    choice = st.sidebar.selectbox(
        f"{title} location",
        options=[CUSTOM_SITE, *LUNAR_SITES],
        format_func=site_label,
        key=f"{prefix}_choice",
    )

    if choice == CUSTOM_SITE:
        lat = st.sidebar.number_input(
            f"{title} latitude (°)",
            min_value=-90.0,
            max_value=90.0,
            value=default_lat,
            step=0.1,
            key=f"{prefix}_lat",
        )
        lon = st.sidebar.number_input(
            f"{title} east longitude (°)",
            min_value=-360.0,
            max_value=360.0,
            value=default_lon,
            step=0.1,
            key=f"{prefix}_lon",
        )
        alt = st.sidebar.number_input(
            f"{title} altitude (km)",
            value=default_alt,
            step=0.1,
            key=f"{prefix}_alt",
        )
    else:
        # Keys include the site id so the locked values refresh when the selection changes.
        site = LUNAR_SITES[choice]
        lat = st.sidebar.number_input(
            f"{title} latitude (°)",
            value=site.latitude_deg,
            format="%.5f",
            disabled=True,
            key=f"{prefix}_lat_{choice}",
        )
        lon = st.sidebar.number_input(
            f"{title} east longitude (°)",
            value=site.longitude_deg_east,
            format="%.5f",
            disabled=True,
            key=f"{prefix}_lon_{choice}",
        )
        alt = st.sidebar.number_input(
            f"{title} altitude (km)",
            value=site.altitude_km,
            format="%.3f",
            disabled=True,
            key=f"{prefix}_alt_{choice}",
        )
        st.sidebar.caption(f"{site.category} · {site.status}")
        st.sidebar.caption(
            f"{site.altitude_basis}. [Coordinate source]({site.source_url})"
        )

    return choice, lat, lon, alt


a_choice, a_lat, a_lon, a_alt = location_inputs("a", "Site A", -89.5, 0.0, 0.0)

compare_enabled = st.sidebar.checkbox(
    "Enable two-site comparison",
    value=True,
)

if compare_enabled:
    st.sidebar.divider()
    b_choice, b_lat, b_lon, b_alt = location_inputs("b", "Site B", -89.5, 30.0, 0.0)

# ---------------------------------------------------------
# SIDEBAR: OBSERVATION PERIOD
# ---------------------------------------------------------

st.sidebar.divider()
st.sidebar.header("Observation period")

selected_date = st.sidebar.date_input(
    "Date",
    value=date(2026, 11, 14),
)

selected_time = st.sidebar.time_input(
    "Start time (UTC)",
    value=time(0, 0),
)

DURATION_OPTIONS = {
    "6 hours": 6,
    "12 hours": 12,
    "24 hours": 24,
    "48 hours": 48,
    "7 days": 24 * 7,
    "14 days": 24 * 14,
    "30 days (about one lunar day)": 24 * 30,
}

duration_label = st.sidebar.selectbox(
    "Duration",
    options=list(DURATION_OPTIONS),
    index=len(DURATION_OPTIONS) - 1,
)

duration_hours = DURATION_OPTIONS[duration_label]

step_minutes = st.sidebar.selectbox(
    "Sampling interval (minutes)",
    options=[60, 30, 15],
    index=1,
)

# ---------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------

if st.button("Analyse lunar location(s)", type="primary"):

    start_datetime = datetime.combine(
        selected_date,
        selected_time,
    )

    end_datetime = start_datetime + timedelta(
        hours=duration_hours
    )

    sites = {
        "Site A": (a_lat, a_lon, a_alt),
    }
    choices = {"Site A": a_choice}

    if compare_enabled:
        sites["Site B"] = (b_lat, b_lon, b_alt)
        choices["Site B"] = b_choice

    results = {}

    try:
        with st.spinner(
            "Retrieving ephemeris data from JPL Horizons..."
        ):

            for site_name, coordinates in sites.items():

                lat, lon, alt = coordinates

                results[site_name] = run_analysis(
                    lat,
                    lon,
                    alt,
                    start_datetime,
                    end_datetime,
                    step_minutes,
                )

        st.success("Analysis completed successfully.")

        st.header("1. Location overview")

        columns = st.columns(len(results))

        for column, (site_name, result) in zip(
            columns, results.items()
        ):

            coordinates = result["summary"]["observer"]

            with column:
                st.subheader(site_name)
                st.write(f"Location: {site_label(choices[site_name])}")
                st.write(
                    f"Latitude: {coordinates['lat_deg']:.2f}°"
                )
                st.write(
                    f"East longitude: "
                    f"{coordinates['lon_deg_east']:.2f}°"
                )
                st.write(
                    f"Altitude: {coordinates['alt_km']:.3f} km"
                )

        # -------------------------------------------------
        # SITE COMPARISON SUMMARY
        # -------------------------------------------------

        section = 2

        if len(results) == 2:

            st.header(f"{section}. Site comparison summary")
            section += 1

            comparison_table, headline = compare_sites(
                results["Site A"]["metrics"],
                results["Site B"]["metrics"],
                "Site A",
                "Site B",
            )

            st.info(headline)

            st.dataframe(
                comparison_table,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "\"More hours\" means more time geometrically above the "
                "horizon during this period. It is not a statement about "
                "usable solar power or communications performance."
            )

        # -------------------------------------------------
        # VISIBILITY METRICS
        # -------------------------------------------------

        st.header(f"{section}. Visibility metrics")
        section += 1

        metric_columns = st.columns(len(results))

        for column, (site_name, result) in zip(
            metric_columns, results.items()
        ):

            metrics = result["metrics"]

            with column:
                st.subheader(site_name)

                st.metric(
                    "Sun above horizon",
                    f"{metrics['sun']['fraction_of_period']:.1%}",
                )

                st.metric(
                    "Earth above horizon",
                    f"{metrics['earth']['fraction_of_period']:.1%}",
                )

                st.metric(
                    "Sun and Earth both above horizon",
                    f"{metrics['both']['fraction_of_period']:.1%}",
                )

                st.dataframe(
                    metrics_table(metrics),
                    use_container_width=True,
                    hide_index=True,
                )

        st.caption(
            "Shares are fractions of the analysed period, calculated "
            "from interpolated horizon-crossing times. A value shown "
            "with \">=\" is cut off by the start or end of the period "
            "and could be longer in reality."
        )

        # -------------------------------------------------
        # ELEVATION CHART
        # -------------------------------------------------

        st.header(f"{section}. Elevation comparison")
        section += 1

        fig = go.Figure()

        for site_name, result in results.items():

            data = result["data"]

            fig.add_trace(
                go.Scatter(
                    x=data["utc"],
                    y=data["sun_el_deg"],
                    mode="lines",
                    name=f"{site_name} - Sun",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=data["utc"],
                    y=data["earth_el_deg"],
                    mode="lines",
                    name=f"{site_name} - Earth",
                    line=dict(dash="dash"),
                )
            )

        fig.add_hline(
            y=0,
            line_dash="dot",
            annotation_text="Lunar horizon",
        )

        fig.update_layout(
            xaxis_title="Time (UTC)",
            yaxis_title="Elevation (degrees)",
            hovermode="x unified",
            legend_title="Observer and target",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        # -------------------------------------------------
        # VISIBILITY WINDOWS
        # -------------------------------------------------

        st.header(f"{section}. Visibility windows")
        section += 1

        for site_name, result in results.items():

            with st.expander(
                f"{site_name} - Detailed visibility windows",
                expanded=True,
            ):

                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Sun**")

                    sun_windows = result["windows"]["sun"]

                    if sun_windows.empty:
                        st.write("No visible interval detected.")
                    else:
                        st.dataframe(
                            sun_windows,
                            use_container_width=True,
                            hide_index=True,
                        )

                with col2:
                    st.write("**Earth**")

                    earth_windows = result["windows"]["earth"]

                    if earth_windows.empty:
                        st.write("No visible interval detected.")
                    else:
                        st.dataframe(
                            earth_windows,
                            use_container_width=True,
                            hide_index=True,
                        )

        # -------------------------------------------------
        # RAW DATA
        # -------------------------------------------------

        st.header(f"{section}. Observation data")

        for site_name, result in results.items():

            with st.expander(f"{site_name} - Raw observations"):

                data = result["data"]

                st.dataframe(
                    data,
                    use_container_width=True,
                    hide_index=True,
                )

                csv = data.to_csv(index=False).encode("utf-8")

                st.download_button(
                    f"Download {site_name} CSV",
                    data=csv,
                    file_name=f"{site_name.lower().replace(' ', '_')}_observations.csv",
                    mime="text/csv",
                    key=f"download_{site_name}",
                )

    except Exception as exc:

        st.error(
            f"Analysis failed: {type(exc).__name__}: {exc}"
        )

# ---------------------------------------------------------
# SCIENTIFIC LIMITATIONS
# ---------------------------------------------------------

st.divider()

st.subheader("Model limitations")

st.write(
    """
    Visibility is determined using the apparent elevation of the
    centre of the Sun and of Earth relative to an ideal geometric
    horizon of 0 degrees. The angular size of each body (about
    0.5 degrees for the Sun and 1.9 degrees for Earth) is not
    modelled.

    This implementation does not account for local terrain,
    obstructions, solar-panel orientation, antenna orientation,
    electrical power generation or communications link budgets.
    Sun above the horizon is geometric illumination, not
    guaranteed usable power. Earth above the horizon is geometric
    line of sight, not a guaranteed communications link.

    Catalogue coordinates are taken from the source linked for each
    site (planetocentric latitude, east longitude, altitude 0 km
    assumed); custom coordinates are user-defined. The application
    does not identify or certify viable landing sites.
    """
)
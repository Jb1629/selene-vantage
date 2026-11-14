
from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lunar_analysis import analyse_lunar_site


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Lunar Mission Browser",
    page_icon="🌕",
    layout="wide",
)

st.title("🌕 Lunar Mission Browser")

st.write(
    "Explore solar illumination and direct Earth visibility "
    "from locations on the lunar surface."
)

st.caption(
    "Ephemeris source: NASA/JPL Horizons. "
    "All displayed observation times are UTC."
)

st.info(
    "The default coordinates (-89.5°, 0°) are an artificial "
    "south-pole test location, not an actual mission landing site."
)


# ---------------------------------------------------------
# SITE AND TIME INPUTS
# ---------------------------------------------------------

st.sidebar.header("Observer location")

latitude = st.sidebar.number_input(
    "Latitude (degrees)",
    min_value=-90.0,
    max_value=90.0,
    value=-89.5,
    step=0.1,
)

longitude = st.sidebar.number_input(
    "East longitude (degrees)",
    min_value=-360.0,
    max_value=360.0,
    value=0.0,
    step=0.1,
)

altitude = st.sidebar.number_input(
    "Altitude (km)",
    value=0.0,
    step=0.1,
    format="%.3f",
)

st.sidebar.header("Observation period")

selected_date = st.sidebar.date_input(
    "Date",
    value=date(2026, 11, 14),
)

selected_time = st.sidebar.time_input(
    "Start time (UTC)",
    value=time(0, 0),
)

duration_hours = st.sidebar.selectbox(
    "Observation duration",
    options=[6, 12, 24, 48],
    index=0,
)

step_minutes = st.sidebar.selectbox(
    "Sampling interval",
    options=[60, 30, 15],
    index=0,
)

horizon_deg = 0.0

st.sidebar.caption(
    "Visibility is defined geometrically as elevation above 0°."
)


# ---------------------------------------------------------
# RUN ANALYSIS
# ---------------------------------------------------------

if st.button("Analyse lunar site", type="primary"):

    start_datetime = datetime.combine(
        selected_date,
        selected_time,
    )

    end_datetime = start_datetime + timedelta(
        hours=duration_hours
    )

    with st.spinner(
        "Retrieving ephemeris data from NASA/JPL Horizons..."
    ):

        try:

            result = analyse_lunar_site(
                lat_deg=latitude,
                lon_deg=longitude,
                alt_km=altitude,
                start=start_datetime,
                end=end_datetime,
                step_minutes=step_minutes,
                horizon_deg=horizon_deg,
            )

            data = result["data"]
            summary = result["summary"]
            windows = result["windows"]

            st.success("Analysis completed successfully.")

            # ---------------------------------------------
            # SITE INFORMATION
            # ---------------------------------------------

            st.header("Observer information")

            col1, col2, col3 = st.columns(3)

            col1.metric("Latitude", f"{latitude:.2f}°")
            col2.metric("East longitude", f"{longitude:.2f}°")
            col3.metric("Altitude", f"{altitude:.3f} km")

            st.write(
                f"**Observation period:** "
                f"{start_datetime:%Y-%m-%d %H:%M} to "
                f"{end_datetime:%Y-%m-%d %H:%M} UTC"
            )

            # ---------------------------------------------
            # VISIBILITY SUMMARY
            # ---------------------------------------------

            st.header("Visibility summary")

            col1, col2 = st.columns(2)

            col1.metric(
                "Sun visible (sampled)",
                f"{summary['sun_visible_sample_fraction']:.1%}",
            )

            col2.metric(
                "Earth visible (sampled)",
                f"{summary['earth_visible_sample_fraction']:.1%}",
            )

            st.caption(
                "These percentages represent sampled observations, "
                "not exact continuous-time visibility."
            )

            # ---------------------------------------------
            # ELEVATION CHART
            # ---------------------------------------------

            st.header("Sun and Earth elevation")

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=data["utc"],
                    y=data["sun_el_deg"],
                    mode="lines",
                    name="Sun elevation",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=data["utc"],
                    y=data["earth_el_deg"],
                    mode="lines",
                    name="Earth elevation",
                )
            )

            fig.add_hline(
                y=0,
                line_dash="dash",
                annotation_text="Lunar horizon",
            )

            fig.update_layout(
                xaxis_title="Time (UTC)",
                yaxis_title="Elevation (degrees)",
                hovermode="x unified",
                legend_title="Target",
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

            # ---------------------------------------------
            # VISIBILITY WINDOWS
            # ---------------------------------------------

            st.header("Visibility windows")

            tab_sun, tab_earth = st.tabs(
                ["☀️ Sun", "🌍 Earth"]
            )

            with tab_sun:

                if windows["sun"].empty:
                    st.write(
                        "The Sun did not rise above the "
                        "horizon during this observation period."
                    )
                else:
                    st.dataframe(
                        windows["sun"],
                        use_container_width=True,
                        hide_index=True,
                    )

            with tab_earth:

                if windows["earth"].empty:
                    st.write(
                        "Earth did not rise above the "
                        "horizon during this observation period."
                    )
                else:
                    st.dataframe(
                        windows["earth"],
                        use_container_width=True,
                        hide_index=True,
                    )

            # ---------------------------------------------
            # RAW OBSERVATIONS
            # ---------------------------------------------

            with st.expander("View underlying observation data"):

                st.dataframe(
                    data,
                    use_container_width=True,
                    hide_index=True,
                )

                csv = data.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "Download observations as CSV",
                    data=csv,
                    file_name="lunar_observations.csv",
                    mime="text/csv",
                )

        except Exception as exc:

            st.error(
                f"Analysis failed: {type(exc).__name__}: {exc}"
            )


# ---------------------------------------------------------
# SCIENTIFIC LIMITATIONS
# ---------------------------------------------------------

st.divider()

st.subheader("About this model")

st.write(
    """
    This application calculates the apparent azimuth and elevation
    of the Sun and Earth as seen from a specified lunar-surface
    observer using JPL Horizons.

    An elevation above 0° indicates geometric visibility above an
    ideal mathematical horizon.

    The current model does not account for local terrain,
    obstructions, solar-panel orientation, antenna orientation,
    power-system performance or communications link budgets.

    Consequently, geometric visibility should not be interpreted
    as guaranteed electrical power or successful communications.
    """
)

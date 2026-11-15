# Selene Vantage

**Lunar Site Visibility & Mission Analysis**  
NASA Space Apps Challenge 2026

[Open the live Streamlit application](https://selene-vantage-f7zatdd9mukmyfoj5vhmxa.streamlit.app/) · [View the source code](https://github.com/Jb1629/selene-vantage)

## Overview

Selene Vantage is an interactive tool for examining the time-dependent geometric visibility of the Sun and Earth from selected locations on the lunar surface. It is designed as a preliminary site-analysis aid for lunar surface mission planning, with particular relevance to illumination and direct Earth line-of-sight considerations for CLPS and other lunar missions.

A user can select two locations from a curated catalogue or enter custom lunar coordinates, choose an observation start time and duration, and compare the apparent azimuth and elevation of the Sun and Earth over the selected period.

The application uses NASA/JPL's Horizons system for ephemerides and presents the results as visibility intervals, summary metrics and time-series plots.

## What it does

- **Two-site comparison:** analyse Site A and Site B over the same observation period.
- **Curated location catalogue:** includes six Apollo Lunar Module landing sites, three completed CLPS landers and four planned CLPS destination-region reference points.
- **Custom coordinates:** enter a latitude, east-positive longitude and altitude for any other lunar observer location.
- **Time controls:** analyse periods of 6 hours, 12 hours, 24 hours, 48 hours, 7 days, 14 days or 30 days, with sampling intervals of 60, 30 or 15 minutes.
- **Geometric visibility:** identify when the Sun and Earth are above the selected geometric horizon.
- **Visibility windows and metrics:** calculate total visible time, percentage of the analysed period, number of windows, longest continuous window, longest gap and maximum/minimum sampled elevation.
- **Simultaneous visibility:** calculate when the Sun and Earth are both above the horizon at the same time.
- **Visual comparison and export:** inspect elevation time series and download observation data as CSV.

## How it works

1. The user selects a catalogue location or supplies custom lunar coordinates.
2. Selene Vantage requests apparent azimuth/elevation observations from the [JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api) for the Sun (target 10) and Earth (target 399), using the Moon (body 301) as the observer's central body.
3. The application checks the Horizons response header to verify the central body, target and echoed observer coordinates. This is intended to catch wrong-body or malformed-coordinate requests; it is not an independent survey of the source coordinates.
4. The sampled elevations are compared with a 0-degree geometric horizon. A body is classed as geometrically visible when its elevation is greater than 0 degrees.
5. Visibility transitions are interpolated between adjacent samples to estimate rise/set times and interval durations. The resulting intervals are combined to calculate site metrics and simultaneous Sun/Earth visibility.
6. Streamlit displays the comparison and Plotly elevation charts; the underlying observations can be downloaded as CSV.

The app caches repeated analyses for a limited period to reduce unnecessary repeat requests to Horizons.

## Location catalogue

The catalogue contains 13 entries:

### Historical Apollo landing sites

Apollo 11, 12, 14, 15, 16 and 17. The catalogue uses the Lunar Module rows in NASA NSSDCA's *Apollo Landing Site Coordinates* table, rather than substituting nearby ALSEP or retroreflector coordinates.

### Completed CLPS landings

- Intuitive Machines IM-1 — Odysseus (Malapert A)
- Intuitive Machines IM-2 — Athena (near Mons Mouton)
- Firefly Blue Ghost Mission 1 (Mare Crisium)

These are represented by published lander positions, not the centres of nearby named features.

### Planned CLPS destination-region references

- Griffin-1 — Nobile Crater
- IM-3 — Reiner Gamma
- IM-4 — Mons Mouton
- Blue Ghost Mission 2 — Nassau Crater

These four entries use the USGS/IAU Gazetteer centre of the named feature as a representative reference point. **They are not asserted landing coordinates, landing ellipses or surveyed touchdown points.** Mission schedules and destinations can change; check the linked mission pages for updates.

Each catalogue record stores its source, coordinate convention, status and notes. The app also preserves manual custom-coordinate input for locations not in the catalogue.

## Scientific scope and limitations

Selene Vantage currently reports **geometric visibility**, not operational readiness or guaranteed service.

- **No local terrain horizon:** the current model uses a 0-degree horizon relative to the lunar reference sphere. It does not ingest local elevation maps or calculate azimuth-dependent obstruction from crater rims, ridges, slopes or boulders.
- **No terrain shadow model:** a positive Sun elevation does not guarantee that a solar array is illuminated at the actual lander position. Local topography, lander orientation, panel orientation and other obstructions are not modelled.
- **No power-system model:** solar visibility is not converted into electrical power, energy storage, battery state or thermal performance.
- **No communications link budget:** Earth above the geometric horizon indicates direct geometric line of sight in this model. It does not guarantee a usable communications link; antenna pointing, terrain obstruction, radio-frequency link budget, network architecture and relay availability are outside scope.
- **Reference-sphere altitude:** catalogue entries currently use 0 km on the 1,737.4 km Horizons lunar reference sphere as a modelling assumption. This is not a claim that each site has zero topographic elevation. Published local elevations are not imported.
- **Sampling and interpolation:** visibility crossings are estimated from discrete time samples using interpolation between adjacent samples. Short events can be missed if the selected sampling interval is too coarse. A metric marked as reaching the start or end of the observation period may continue beyond the selected interval.
- **Coordinate provenance:** Apollo coordinates are documented by NASA NSSDCA in the Mean Earth/Polar Axis lunar reference system (DE421). The NSSDCA CLPS landing table does not explicitly state its coordinate reference frame; those published values are retained with that limitation recorded. Planned feature-centre coordinates use the USGS/IAU Gazetteer's planetographic convention. On the spherical lunar figure used by Horizons, planetographic and planetocentric latitude coincide.

For these reasons, the application should be treated as a preliminary geometric screening and comparison tool, not a replacement for detailed mission engineering, terrain analysis or communications/power modelling.

## Technology

- Python
- Streamlit
- Plotly
- pandas
- requests
- NASA/JPL Horizons API

Dependency versions are pinned in [`requirements.txt`](requirements.txt).

## Run locally

Python 3.13.9 was used during development. From the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app_stage4.py
```

The application makes live requests to the JPL Horizons API. Network access is required for new, uncached analyses.

## Tests and validation

Run the automated test suite:

```powershell
python -m pytest
```

Run the catalogue's live Horizons observer/header checks:

```powershell
python check_catalogue_horizons.py
```

The live check makes network requests for catalogue sites. It verifies that Horizons identifies the Moon as the central body and echoes the requested observer coordinates within the script's tolerances. This guards against common request-configuration errors; it does not prove the underlying source coordinates or coordinate-frame assumptions are error-free.

## Data and references

- [NASA/JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api) — apparent Sun and Earth azimuth/elevation observations from lunar-surface observers.
- [NASA NSSDCA — Apollo Landing Site Coordinates](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html) — Apollo Lunar Module coordinates and stated reference frame.
- [NASA NSSDCA — Table of Anthropogenic Impacts and Spacecraft on the Moon](https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_artifact_impacts.html) — published lunar spacecraft/lander locations used for the CLPS catalogue.
- [LROC — Odysseus landing site](https://www.lroc.asu.edu/posts/1360), [Athena landing site](https://www.lroc.asu.edu/images/1408) and [Blue Ghost Mission 1 landing site](https://www.lroc.asu.edu/images/1406) — landing-site imagery and corroborating context.
- [USGS/IAU Gazetteer of Planetary Nomenclature](https://planetarynames.wr.usgs.gov/) — named lunar-feature centres used as representative points for planned destination regions: [Nobile](https://planetarynames.wr.usgs.gov/Feature/4321), [Reiner Gamma](https://planetarynames.wr.usgs.gov/Feature/4987), [Mons Mouton](https://planetarynames.wr.usgs.gov/Feature/16070) and [Nassau](https://planetarynames.wr.usgs.gov/Feature/4159).
- Mission destination context: [NASA — Griffin-1](https://www.nasa.gov/event/clps-flight-astrobotics-griffin-mission-one/), [NASA — IM-3](https://www.nasa.gov/event/clps-flight-intuitive-machines-im-3/), [NASA — IM-4](https://www.nasa.gov/event/clps-flight-intuitive-machines-im-4-2/) and [Firefly — Blue Ghost Mission 2](https://fireflyspace.com/missions/blue-ghost-mission-2/).

The catalogue records the direct source URL and site-specific notes for each location in [`lunar_sites.py`](lunar_sites.py).

## AI-use disclosure

AI assistants (ChatGPT and Claude) were used during development for technical planning, code drafting and refinement, debugging, test design and documentation. The project author selected the scope and implementation approach, reviewed and adapted generated material, checked catalogue coordinates against cited NASA/USGS sources, and ran local automated tests and live JPL Horizons checks. AI-generated suggestions and code were not treated as authoritative scientific sources; source claims and limitations are documented above and in the catalogue.

## Future work

- Integrate Lunar Reconnaissance Orbiter Lunar Orbiter Laser Altimeter (LOLA) elevation data to derive local, azimuth-dependent terrain-horizon profiles.
- Add terrain-aware illumination and line-of-sight calculations.
- Extend the catalogue as additional authoritative landing coordinates and mission target data become available.
- Add mission-specific power and communications constraints where the necessary engineering data are available.

## Project status

This is a NASA Space Apps Challenge 2026 prototype. It is an educational and preliminary analysis tool; it is not certified for operational mission planning.

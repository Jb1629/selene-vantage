import pandas as pd

from lunar_analysis import find_visibility_windows
from lunar_metrics import (
    compare_sites,
    complement_intervals,
    compute_site_metrics,
    intersect_intervals,
    metrics_table,
)

T0 = pd.Timestamp("2026-11-13 00:00", tz="UTC")


def h(hours):
    return T0 + pd.Timedelta(hours=hours)


def close(a, b, tol=1e-9):
    return abs(a - b) < tol


def build(sun_el, earth_el):
    return pd.DataFrame({
        "utc": [h(i) for i in range(len(sun_el))],
        "sun_el_deg": sun_el,
        "earth_el_deg": earth_el,
    })


def metrics_for(df):
    return compute_site_metrics(
        df,
        find_visibility_windows(df, "sun"),
        find_visibility_windows(df, "earth"),
    )


def test_intersect_intervals():
    a = [(h(0), h(3)), (h(5), h(8))]
    b = [(h(2), h(6)), (h(7), h(9))]
    assert intersect_intervals(a, b) == [(h(2), h(3)), (h(5), h(6)), (h(7), h(8))]
    assert intersect_intervals(a, []) == []


def test_complement_intervals():
    iv = [(h(1), h(2)), (h(4), h(5))]
    assert complement_intervals(iv, h(0), h(6)) == [
        (h(0), h(1)), (h(2), h(4)), (h(5), h(6))
    ]
    assert complement_intervals([], h(0), h(6)) == [(h(0), h(6))]
    assert complement_intervals([(h(0), h(6))], h(0), h(6)) == []


def test_synthetic_sun_case():
    # Same artificial data as the Stage 2 interpolation test:
    # rise 00:30, set 02:45, duration 2.25 h.
    m = metrics_for(build([-1.0, 1.0, 3.0, -1.0], [-5.0] * 4))
    sun, earth, both = m["sun"], m["earth"], m["both"]

    assert close(m["period_hours"], 3.0)
    assert close(sun["total_hours"], 2.25)
    assert close(sun["fraction_of_period"], 0.75)
    assert sun["n_windows"] == 1
    assert close(sun["longest_hours"], 2.25) and not sun["longest_truncated"]
    assert close(sun["longest_gap_hours"], 0.5) and sun["longest_gap_truncated"]
    assert close(sun["max_el_deg"], 3.0) and close(sun["min_el_deg"], -1.0)

    assert earth["total_hours"] == 0.0 and earth["n_windows"] == 0
    assert close(earth["longest_gap_hours"], 3.0) and earth["longest_gap_truncated"]
    assert both["total_hours"] == 0.0


def test_two_window_overlap_case():
    # Sun up 0-1.5 and 3.5-6; Earth up 0.5-4.5; both up 0.5-1.5 and 3.5-4.5.
    m = metrics_for(build(
        [1, 1, -1, -1, 1, 1, 1],
        [-1, 1, 1, 1, 1, -1, -1],
    ))
    sun, earth, both = m["sun"], m["earth"], m["both"]

    assert close(m["period_hours"], 6.0)

    assert close(sun["total_hours"], 4.0) and sun["n_windows"] == 2
    assert close(sun["longest_hours"], 2.5) and sun["longest_truncated"]
    assert close(sun["longest_gap_hours"], 2.0) and not sun["longest_gap_truncated"]

    assert close(earth["total_hours"], 4.0) and earth["n_windows"] == 1
    assert close(earth["longest_hours"], 4.0) and not earth["longest_truncated"]
    assert close(earth["longest_gap_hours"], 1.5) and earth["longest_gap_truncated"]

    assert close(both["total_hours"], 2.0) and both["n_windows"] == 2
    assert close(both["longest_hours"], 1.0) and not both["longest_truncated"]
    assert close(both["longest_gap_hours"], 2.0) and not both["longest_gap_truncated"]


def test_validated_south_pole_regression():
    # The seven real Horizons rows for -89.5 lat, 0 lon, 0 km,
    # 2026-11-13 00:00-06:00 UTC, 60-minute steps.
    sun_el = [1.179423, 1.182420, 1.185445, 1.188496, 1.191574, 1.194678, 1.197808]
    earth_el = [-5.057530, -5.023869, -4.989822, -4.955392,
                -4.920581, -4.885392, -4.849827]
    m = metrics_for(build(sun_el, earth_el))
    sun, earth, both = m["sun"], m["earth"], m["both"]

    assert close(m["period_hours"], 6.0)

    assert close(sun["total_hours"], 6.0)
    assert close(sun["fraction_of_period"], 1.0)
    assert sun["n_windows"] == 1
    assert close(sun["longest_hours"], 6.0) and sun["longest_truncated"]
    assert sun["longest_gap_hours"] == 0.0 and not sun["longest_gap_truncated"]

    assert earth["total_hours"] == 0.0 and earth["n_windows"] == 0
    assert close(earth["longest_gap_hours"], 6.0) and earth["longest_gap_truncated"]

    assert both["total_hours"] == 0.0


def test_metrics_table():
    m = metrics_for(build(
        [1, 1, -1, -1, 1, 1, 1],
        [-1, 1, 1, 1, 1, -1, -1],
    ))
    t = metrics_table(m)
    assert list(t.columns) == ["Metric", "Sun", "Earth", "Both"]

    longest = t.loc[t["Metric"] == "Longest continuous window (h)"].iloc[0]
    assert longest["Sun"] == ">= 2.50"   # touches the end of the period
    assert longest["Earth"] == "4.00"
    assert longest["Both"] == "1.00"

    elevation = t.loc[t["Metric"] == "Max sampled elevation (deg)"].iloc[0]
    assert elevation["Both"] == "n/a"


def test_compare_sites():
    overlap = metrics_for(build(
        [1, 1, -1, -1, 1, 1, 1],
        [-1, 1, 1, 1, 1, -1, -1],
    ))
    pole = metrics_for(build(
        [1.179423, 1.182420, 1.185445, 1.188496, 1.191574, 1.194678, 1.197808],
        [-5.057530, -5.023869, -4.989822, -4.955392, -4.920581, -4.885392, -4.849827],
    ))

    table, headline = compare_sites(overlap, pole, "Site A", "Site B")
    rows = table.set_index("Measure")

    assert rows.loc["Sun above horizon (h)", "More hours"] == "Site B"      # 6.00 vs 4.00
    assert rows.loc["Earth above horizon (h)", "More hours"] == "Site A"    # 4.00 vs 0.00
    assert rows.loc["Sun and Earth both above horizon (h)", "More hours"] == "Site A"
    assert headline.startswith("Site A has more time")
    assert "2.0 h versus 0.0 h over 6.0 h" in headline

    # Neither site ever has both up
    _, none_headline = compare_sites(pole, pole, "Site A", "Site B")
    assert none_headline.startswith("Neither site")

    # Identical sites tie
    table_same, same_headline = compare_sites(overlap, overlap, "Site A", "Site B")
    assert set(table_same["More hours"]) == {"Tie"}
    assert same_headline.startswith("Both sites have about the same")


if __name__ == "__main__":
    tests = [
        fn for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} tests passed")
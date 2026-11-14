"""
lunar_metrics.py

Continuous-time summary metrics for the lunar site analysis.

These functions work on the visibility *windows* returned by
lunar_analysis.find_visibility_windows(), so every number here is based on
interpolated horizon-crossing times, not on sample counts.

"Visible" means geometrically above the chosen horizon elevation. It does NOT
mean usable solar power or a working communications link.

Truncation: the analysis period ends at the first and last observation. A
window or gap that touches either end of the period may really be longer than
the period shows, so its duration is only a lower bound. Every such value is
flagged as truncated (and shown with ">=" in metrics_table()).
"""

import pandas as pd


def _hours(start, end):
    return (end - start).total_seconds() / 3600.0


def windows_to_intervals(windows):
    """Convert a windows DataFrame into a sorted list of (start, end) tuples."""
    if windows is None or len(windows) == 0:
        return []

    starts = pd.to_datetime(windows["start_utc"], utc=True)
    ends = pd.to_datetime(windows["end_utc"], utc=True)

    intervals = sorted(zip(starts, ends))
    return [(s, e) for s, e in intervals if e > s]


def intersect_intervals(a, b):
    """Intersection of two sorted, non-overlapping interval lists."""
    result = []
    i = j = 0

    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])

        if end > start:
            result.append((start, end))

        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1

    return result


def complement_intervals(intervals, start, end):
    """Gaps between intervals inside the period [start, end]."""
    gaps = []
    cursor = start

    for s, e in intervals:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)

    if cursor < end:
        gaps.append((cursor, end))

    return gaps


def _longest(intervals, start, end):
    """(hours, start, end, touches_period_edge) of the longest interval."""
    if not intervals:
        return 0.0, None, None, False

    s, e = max(intervals, key=lambda iv: _hours(iv[0], iv[1]))
    return _hours(s, e), s, e, (s <= start or e >= end)


def summarise_intervals(intervals, start, end):
    """Totals, longest interval and longest gap for one set of intervals."""
    period = _hours(start, end)
    total = sum(_hours(s, e) for s, e in intervals)

    gaps = complement_intervals(intervals, start, end)

    lh, ls, le, lt = _longest(intervals, start, end)
    gh, gs, ge, gt = _longest(gaps, start, end)

    return {
        "total_hours": total,
        "fraction_of_period": total / period if period > 0 else 0.0,
        "n_windows": len(intervals),
        "longest_hours": lh,
        "longest_start_utc": ls,
        "longest_end_utc": le,
        "longest_truncated": lt,
        "longest_gap_hours": gh,
        "longest_gap_start_utc": gs,
        "longest_gap_end_utc": ge,
        "longest_gap_truncated": gt,
    }


def elevation_stats(data, column):
    """Min/max/mean of the *sampled* elevations (true extremes may fall between samples)."""
    values = pd.to_numeric(data[column], errors="raise")
    return {
        "max_el_deg": float(values.max()),
        "min_el_deg": float(values.min()),
        "mean_el_deg": float(values.mean()),
    }


def compute_site_metrics(data, sun_windows, earth_windows):
    """
    Metrics for one site.

    data          - DataFrame with utc, sun_el_deg, earth_el_deg
    sun_windows   - output of find_visibility_windows(..., target="sun")
    earth_windows - output of find_visibility_windows(..., target="earth")

    Returns {"period_hours", "sun", "earth", "both"}, where "both" covers
    the times the Sun AND Earth are above the horizon together.
    """
    times = pd.to_datetime(data["utc"], utc=True)
    start, end = times.iloc[0], times.iloc[-1]

    sun_iv = windows_to_intervals(sun_windows)
    earth_iv = windows_to_intervals(earth_windows)
    both_iv = intersect_intervals(sun_iv, earth_iv)

    return {
        "period_hours": _hours(start, end),
        "sun": {
            **summarise_intervals(sun_iv, start, end),
            **elevation_stats(data, "sun_el_deg"),
        },
        "earth": {
            **summarise_intervals(earth_iv, start, end),
            **elevation_stats(data, "earth_el_deg"),
        },
        "both": summarise_intervals(both_iv, start, end),
    }


def _fmt(value, truncated=False, digits=2):
    if value is None:
        return "n/a"
    text = f"{value:.{digits}f}"
    return f">= {text}" if truncated else text


def metrics_table(metrics):
    """Display-ready DataFrame (Metric, Sun, Earth, Both) built from compute_site_metrics()."""
    sun, earth, both = metrics["sun"], metrics["earth"], metrics["both"]

    def row(label, key, digits=2, scale=1.0, truncated_key=None, groups=(sun, earth, both)):
        cells = []
        for g in groups:
            if key not in g:
                cells.append("n/a")
                continue
            truncated = bool(g[truncated_key]) if truncated_key else False
            cells.append(_fmt(g[key] * scale, truncated, digits))
        return [label] + cells

    rows = [
        row("Total time above horizon (h)", "total_hours"),
        row("Share of period (%)", "fraction_of_period", digits=1, scale=100.0),
        row("Number of windows", "n_windows", digits=0),
        row("Longest continuous window (h)", "longest_hours",
            truncated_key="longest_truncated"),
        row("Longest gap (h)", "longest_gap_hours",
            truncated_key="longest_gap_truncated"),
        row("Max sampled elevation (deg)", "max_el_deg"),
        row("Min sampled elevation (deg)", "min_el_deg"),
    ]

    return pd.DataFrame(rows, columns=["Metric", "Sun", "Earth", "Both"])


def compare_sites(metrics_a, metrics_b, name_a="Site A", name_b="Site B",
                  tolerance_hours=0.01):
    """
    Compare two sites over the same period.

    Returns (table, headline). "More hours" means more time geometrically above
    the horizon over the period. It is not a statement about power or
    communications performance. The headline is based on the time the Sun and
    Earth are above the horizon together.
    """
    measures = [
        ("Sun above horizon (h)", "sun"),
        ("Earth above horizon (h)", "earth"),
        ("Sun and Earth both above horizon (h)", "both"),
    ]

    rows = []
    for label, key in measures:
        a = metrics_a[key]["total_hours"]
        b = metrics_b[key]["total_hours"]

        if abs(a - b) <= tolerance_hours:
            more = "Tie"
        else:
            more = name_a if a > b else name_b

        rows.append({
            "Measure": label,
            name_a: f"{a:.2f}",
            name_b: f"{b:.2f}",
            "More hours": more,
        })

    table = pd.DataFrame(rows, columns=["Measure", name_a, name_b, "More hours"])

    a_both = metrics_a["both"]["total_hours"]
    b_both = metrics_b["both"]["total_hours"]
    period = metrics_a["period_hours"]

    if a_both <= tolerance_hours and b_both <= tolerance_hours:
        headline = (
            "Neither site has the Sun and Earth above the horizon at the "
            "same time during this period."
        )
    elif abs(a_both - b_both) <= tolerance_hours:
        headline = (
            f"Both sites have about the same time with the Sun and Earth "
            f"above the horizon together ({a_both:.1f} h of {period:.1f} h)."
        )
    else:
        winner, w_h, l_h = (
            (name_a, a_both, b_both) if a_both > b_both else (name_b, b_both, a_both)
        )
        headline = (
            f"{winner} has more time with the Sun and Earth both above the "
            f"horizon: {w_h:.1f} h versus {l_h:.1f} h over {period:.1f} h."
        )

    return table, headline
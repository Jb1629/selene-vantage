
import pandas as pd
from lunar_analysis import find_visibility_windows

df = pd.DataFrame({
    "utc": pd.date_range(
        "2026-11-13 00:00",
        periods=4,
        freq="1h",
        tz="UTC"
    ),
    "sun_el_deg": [-1.0, 1.0, 3.0, -1.0],
    "earth_el_deg": [-5.0, -5.0, -5.0, -5.0],
})

windows = find_visibility_windows(df, target="sun")

print(windows.to_string(index=False))

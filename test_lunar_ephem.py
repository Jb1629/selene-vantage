from lunar_ephem import get_sun_earth_azel

df = get_sun_earth_azel(
    lat_deg=-89.5,
    lon_deg=0.0,
    alt_km=0.0,
    start="2026-11-13 00:00",
    end="2026-11-13 06:00",
    step_minutes=60,
)

print(df.to_string(index=False))
print("\nVerification:")
print(df.attrs["verified"])
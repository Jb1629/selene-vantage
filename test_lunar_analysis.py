from lunar_analysis import analyse_lunar_site

result = analyse_lunar_site(
    lat_deg=-89.5,
    lon_deg=0.0,
    alt_km=0.0,
    start="2026-11-13 00:00",
    end="2026-11-13 06:00",
    step_minutes=60,
)

print("\n========== SUMMARY ==========")
for key, value in result["summary"].items():
    print(f"{key}: {value}")

print("\n========== SUN VISIBILITY ==========")
print(result["windows"]["sun"].to_string(index=False))

print("\n========== EARTH VISIBILITY ==========")
print(result["windows"]["earth"].to_string(index=False))

print("\n========== OBSERVATION DATA ==========")
print(result["data"].to_string(index=False))

"""
EXTRACT step — Live AQI Dashboard — Real-Time Diwali Air Data.

Pulls hourly PM2.5 / PM10 for 11 Indian cities from the Open-Meteo Air
Quality API (CAMS — Copernicus Atmosphere Monitoring Service modelled
data; free, no API key) and saves each city's response untouched to
data/raw/.

Window: --start/--end (default: the pre-Diwali build-up, 25 Oct 2026
through today IST). Diwali / Lakshmi Puja 2026 is Sunday 8 Nov, so the
pipeline watches air quality climb toward the festival, through the
night itself, and back down the other side.

Why CAMS and not the WAQI "demo" token: the demo token returns the same
Shanghai demo station for every city — fake data. CAMS is modelled
rather than ground-station data, and we label it as such everywhere;
the pipeline swaps to CPCB station feeds the day a real token exists.

Standard library only (urllib).

Run:  python extract.py [--start 2026-10-25] [--end 2026-11-09]
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://air-quality-api.open-meteo.com/v1/air-quality"
BASE = Path(__file__).parent
RAW_DIR = BASE / "data" / "raw"

# city, state, latitude, longitude — capitals + the NCR pair + big metros
CITIES = [
    ("Delhi", "Delhi", 28.61, 77.21),
    ("Gurugram", "Haryana", 28.46, 77.03),
    ("Mumbai", "Maharashtra", 19.08, 72.88),
    ("Kolkata", "West Bengal", 22.57, 88.36),
    ("Chennai", "Tamil Nadu", 13.08, 80.27),
    ("Bengaluru", "Karnataka", 12.97, 77.59),
    ("Hyderabad", "Telangana", 17.39, 78.49),
    ("Lucknow", "Uttar Pradesh", 26.85, 80.95),
    ("Patna", "Bihar", 25.59, 85.14),
    ("Jaipur", "Rajasthan", 26.91, 75.79),
    ("Ahmedabad", "Gujarat", 23.03, 72.59),
]


def fetch(city: str, lat: float, lon: float, start: date, end: date) -> dict:
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "pm2_5,pm10",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "timezone": "Asia/Kolkata",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "live-aqi-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> int:
    today_ist = date.today()
    parser = argparse.ArgumentParser(description="Extract CAMS air quality for Indian cities")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 10, 25))
    parser.add_argument("--end", type=date.fromisoformat, default=today_ist)
    args = parser.parse_args()
    if args.end < args.start:
        print("--end must not be before --start.")
        return 1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    total_hours = 0
    for city, state, lat, lon in CITIES:
        data = fetch(city, lat, lon, args.start, args.end)
        hours = len(data.get("hourly", {}).get("time", []))
        if not hours:
            print(f"{city}: API returned no hours — refusing to save an empty raw file.")
            return 1
        payload = {"city": city, "state": state, "latitude": lat, "longitude": lon,
                   "response": data}
        name = city.lower().replace(" ", "_") + ".json"
        (RAW_DIR / name).write_text(json.dumps(payload), encoding="utf-8")
        total_hours += hours
        print(f"{city:<10} {hours:>4} hourly rows  -> data/raw/{name}")
    print(f"Cities: {len(CITIES)} | window {args.start} → {args.end} (IST) "
          f"| {total_hours} city-hours extracted")
    return 0


if __name__ == "__main__":
    sys.exit(main())

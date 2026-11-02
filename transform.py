"""
TRANSFORM step — Live AQI Dashboard (Real-Time Diwali Air Data).

Flattens the raw per-city CAMS responses into one tidy hourly table and
computes the INDIAN AQI for every hour from PM2.5 / PM10 using the CPCB
breakpoint method — the same piecewise-linear sub-index formula the
national AQI uses:

    sub-index = I_lo + (C - C_lo) * (I_hi - I_lo) / (C_hi - C_lo)
    AQI       = max(sub-index PM2.5, sub-index PM10)

Honesty note: the official AQI is computed from 24-hour average station
concentrations. Ours is an hourly *indicative* AQI from modelled (CAMS)
concentrations — labelled as such on the dashboard, and the daily view
uses daily-mean concentrations, which is much closer to the official
method. Data-quality checks fail loudly, as in the sister pipelines.

Run:  python transform.py   (after extract.py)
"""

import json
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
RAW_DIR = BASE / "data" / "raw"
OUT_PATH = BASE / "data" / "processed" / "aqi_clean.csv"

# CPCB breakpoint tables: (conc_lo, conc_hi, aqi_lo, aqi_hi), µg/m³
PM25_BANDS = [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
              (91, 120, 201, 300), (121, 250, 301, 400), (251, 380, 401, 500)]
PM10_BANDS = [(0, 50, 0, 50), (51, 100, 51, 100), (101, 200, 101, 200),
              (201, 300, 201, 300), (301, 400, 301, 400), (401, 500, 401, 500)]


def sub_index(conc: float, bands) -> float:
    if conc is None or pd.isna(conc):
        return float("nan")
    for c_lo, c_hi, i_lo, i_hi in bands:
        if conc <= c_hi:
            return i_lo + (conc - c_lo) * (i_hi - i_lo) / (c_hi - c_lo)
    return 500.0  # above the last band: capped at Severe ceiling


def indian_aqi(pm25: float, pm10: float):
    """Return (aqi, dominant_pollutant) from the two sub-indices."""
    s25, s10 = sub_index(pm25, PM25_BANDS), sub_index(pm10, PM10_BANDS)
    if pd.isna(s25) and pd.isna(s10):
        return float("nan"), ""
    if pd.isna(s10) or (not pd.isna(s25) and s25 >= s10):
        return round(s25), "PM2.5"
    return round(s10), "PM10"


def category_for(aqi: float) -> str:
    if pd.isna(aqi):
        return ""
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def main() -> int:
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        print("No raw files — run extract.py first.")
        return 1
    rows = []
    for fp in files:
        payload = json.loads(fp.read_text(encoding="utf-8"))
        hourly = payload["response"]["hourly"]
        for ts, pm25, pm10 in zip(hourly["time"], hourly["pm2_5"], hourly["pm10"]):
            rows.append({
                "city": payload["city"], "state": payload["state"],
                "ts_ist": ts.replace("T", " "),
                "pm25": pm25, "pm10": pm10,
            })
    df = pd.DataFrame(rows)
    raw_count = len(df)

    # --- cleaning (explicit rules) --------------------------------------
    df = df.dropna(subset=["pm25", "pm10"], how="all")
    df = df.drop_duplicates(subset=["city", "ts_ist"])
    df = df.sort_values(["city", "ts_ist"]).reset_index(drop=True)

    aqi_pairs = [indian_aqi(r.pm25, r.pm10) for r in df.itertuples()]
    df["aqi"] = [int(a) if not pd.isna(a) else None for a, _ in aqi_pairs]
    df["dominant"] = [d for _, d in aqi_pairs]
    df["category"] = [category_for(a) for a in df["aqi"]]
    df["date"] = df["ts_ist"].str.slice(0, 10)

    # --- data-quality checks (fail loudly) ------------------------------
    problems = []
    if df.duplicated(subset=["city", "ts_ist"]).any():
        problems.append("duplicate (city, timestamp) rows remain")
    for col in ("pm25", "pm10"):
        if not df[col].dropna().between(0, 1200).all():
            problems.append(f"{col} outside sane range (0..1200 µg/m³)")
    if not df["aqi"].dropna().between(0, 500).all():
        problems.append("computed AQI outside 0..500")
    if df["ts_ist"].isna().any():
        problems.append("unparsed timestamps present")
    if problems:
        for p in problems:
            print(f"QUALITY CHECK FAILED: {p}")
        return 1

    cols = ["city", "state", "ts_ist", "date", "pm25", "pm10",
            "aqi", "category", "dominant"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[cols].to_csv(OUT_PATH, index=False)

    print(f"Raw city-hours : {raw_count}")
    print(f"Clean rows     : {len(df)} ({raw_count - len(df)} removed)")
    print(f"Window (IST)   : {df['ts_ist'].min()} → {df['ts_ist'].max()}")
    print(f"Cities         : {df['city'].nunique()}")
    print(f"Saved (clean)  : data/processed/{OUT_PATH.name}")
    print("All quality checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

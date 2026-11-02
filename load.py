"""
LOAD step — Live AQI Dashboard (Real-Time Diwali Air Data).

Reads the cleaned CSV from transform.py and upserts every hourly row
into SQLite (data/aqi.db). (city, ts_ist) is the PRIMARY KEY and rows
are written with INSERT OR REPLACE in one transaction, so re-running
the pipeline over the same window adds zero duplicates — and when CAMS
revises a past hour's values, the stored row updates in place.

Standard library only (sqlite3 + csv).

Run:  python load.py   (after transform.py)
"""

import csv
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent
CSV_PATH = BASE / "data" / "processed" / "aqi_clean.csv"
SCHEMA_PATH = BASE / "sql" / "schema.sql"
DB_PATH = BASE / "data" / "aqi.db"

COLUMNS = ["city", "state", "ts_ist", "date", "pm25", "pm10",
           "aqi", "category", "dominant"]
FLOATS = {"pm25", "pm10"}
INTS = {"aqi"}

UPSERT_SQL = f"""
INSERT OR REPLACE INTO readings ({", ".join(COLUMNS)})
VALUES ({", ".join("?" for _ in COLUMNS)})
"""


def read_clean_csv(path: Path) -> list[tuple]:
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not found — run transform.py first.")
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            row = []
            for col in COLUMNS:
                v = rec[col]
                if col in FLOATS:
                    row.append(float(v) if v != "" else None)
                elif col in INTS:
                    row.append(int(float(v)) if v != "" else None)
                else:
                    row.append(v)
            rows.append(tuple(row))
    return rows


def main() -> int:
    rows = read_clean_csv(CSV_PATH)
    if not rows:
        print("Clean CSV is empty — nothing to load.")
        return 1
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        before = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        with conn:
            conn.executemany(UPSERT_SQL, rows)
        after, first, last = conn.execute(
            "SELECT COUNT(*), MIN(ts_ist), MAX(ts_ist) FROM readings").fetchone()
    finally:
        conn.close()
    print(f"Clean CSV rows : {len(rows)}")
    print(f"Table before   : {before} rows")
    print(f"Table after    : {after} rows ({after - before:+d} net new)")
    print(f"Coverage (IST) : {first}  →  {last}")
    print(f"Database       : data/{DB_PATH.name}")
    print("Load complete — safe to re-run, hours upsert by (city, timestamp).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

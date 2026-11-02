# 🪔 Live AQI Dashboard — Real-Time Diwali Air Data

An end-to-end data pipeline that tracks air quality across **11 Indian
cities** as the country heads into **Diwali (Lakshmi Puja, Sunday 8 Nov
2026)** — the week when India's air reliably gets its worst of the year.

Hourly PM2.5 / PM10 → **Indian AQI computed with the CPCB breakpoint
formula** → SQLite time series → a self-contained, Diwali-themed
dashboard that rebuilds from the database on every run.

**Live dashboard:** https://live-aqi-dashboard.vercel.app

```
Open-Meteo Air Quality API (CAMS)                CPCB breakpoints
  11 cities · hourly PM2.5/PM10  ──extract──▶  raw JSON (untouched)
                                                      │ transform (pandas,
                                                      ▼  quality checks)
                              indian_aqi(pm25, pm10) ─┴─▶ clean CSV
                                                      │ load (idempotent upsert
                                                      ▼  on city+timestamp)
                                              SQLite time series
                                                      │ build_dashboard (SQL)
                                                      ▼
                                          site/index.html  ──▶ Vercel
```

## Why this project

Every Diwali, firecrackers + winter inversion + stubble smoke push
Delhi-NCR's AQI into Poor–Severe. This pipeline watches that story with
data instead of headlines: a clean baseline week, the festival build-up,
Diwali night itself, and the recovery — all queryable in SQL.

## Design decisions

- **Indian AQI, computed — not copied.** Sub-indices for PM2.5 and PM10
  are computed from CPCB's breakpoint tables with the official
  piecewise-linear formula; AQI = max of the two; categories Good →
  Severe. Daily figures use daily-mean concentrations (the official
  method); hourly figures are labelled *indicative*.
- **Honest source.** Concentrations are **CAMS modelled data** via the
  free Open-Meteo Air Quality API (no key needed). Modelled data is
  smoother than ground stations, so values read lower than a CPCB
  station on the same street — the dashboard footer says exactly this.
  (The popular WAQI "demo" token was rejected: it returns one Shanghai
  demo station for every city.)
- **Idempotent by construction.** `(city, ts_ist)` is the primary key;
  loads use `INSERT OR REPLACE` in one transaction. Verified: re-running
  the same window adds **+0 net new rows**, and CAMS revisions update
  rows in place.
- **"Right now" means arrived hours only.** CAMS also returns forecast
  hours for later today; the dashboard's current-conditions section
  filters to hours ≤ the current IST hour so a forecast never poses as
  a reading.

## What the data showed (first run, 2 Nov 2026)

- **2,376 city-hours** loaded (11 cities × Oct 25 – Nov 2, 2026 IST),
  all quality checks passed.
- Right now (2 Nov, 16:00 IST): **Gurugram worst at AQI 190**, Delhi 166
  (both Moderate, top of the band), Chennai cleanest at **12 (Good)**;
  11-city average **72 (Satisfactory)**.
- **Delhi's build-up is real**: daily average AQI 51 on Oct 30 →
  135 (Oct 31) → 181 (Nov 1) → **244 on Nov 2** — climbing toward
  Diwali, with an earlier peak of **272 on Oct 26**.

## Run it

```bash
pip install -r requirements.txt   # pandas only — extract/load are stdlib

./run_pipeline.sh                          # 25 Oct 2026 → today
./run_pipeline.sh --start 2026-11-01 --end 2026-11-12   # custom window
```

Then open `site/index.html`, or query `data/aqi.db` with the queries in
`sql/analysis_queries.sql` (latest per city, build-up delta, worst
hours, category distribution).

## Files

| File | Role |
|---|---|
| `extract.py` | CAMS hourly PM2.5/PM10 for 11 cities → `data/raw/*.json` |
| `transform.py` | Flatten + CPCB-breakpoint Indian AQI + quality checks → clean CSV |
| `load.py` | Idempotent SQLite upsert into `data/aqi.db` |
| `build_dashboard.py` | SQL → self-contained `site/index.html` |
| `sql/schema.sql` | `readings` table |
| `sql/analysis_queries.sql` | The analysis behind the dashboard's numbers |
| `run_pipeline.sh` | One-command end-to-end run |

## Roadmap

- Swap CAMS for live CPCB station feeds (WAQI token) when available;
  the transform/load contract doesn't change.
- Keep collecting through Diwali night (8 Nov) and publish the spike vs
  baseline comparison.
- Optional: a `--live` poll loop during Diwali week (every 30 min).

Third project in a small ETL series — see also
[open-data-etl-pipeline](https://github.com/dxhanjay/open-data-etl-pipeline)
(weather → SQLite/PostgreSQL) and
[earthquake-etl-pipeline](https://github.com/dxhanjay/earthquake-etl-pipeline)
(USGS → live dashboard).

MIT License.

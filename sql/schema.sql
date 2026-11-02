-- Live AQI Dashboard — readings table.
-- One row per (city, hour IST). The primary key makes loads idempotent:
-- re-extracting the same window upserts the same hours, never duplicates.
CREATE TABLE IF NOT EXISTS readings (
    city      TEXT    NOT NULL,
    state     TEXT    NOT NULL,
    ts_ist    TEXT    NOT NULL,           -- 'YYYY-MM-DD HH:MM' (Asia/Kolkata)
    date      TEXT    NOT NULL,           -- 'YYYY-MM-DD'
    pm25      REAL,                       -- µg/m³, CAMS modelled
    pm10      REAL,                       -- µg/m³, CAMS modelled
    aqi       INTEGER,                    -- Indian AQI, CPCB breakpoints (hourly indicative)
    category  TEXT,                       -- Good / Satisfactory / Moderate / Poor / Very Poor / Severe
    dominant  TEXT,                       -- PM2.5 or PM10
    PRIMARY KEY (city, ts_ist)
);
CREATE INDEX IF NOT EXISTS idx_readings_date ON readings (date);
CREATE INDEX IF NOT EXISTS idx_readings_city_ts ON readings (city, ts_ist);

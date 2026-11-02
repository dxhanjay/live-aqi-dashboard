-- Live AQI Dashboard — analysis queries (all executed against data/aqi.db)
-- Indian AQI computed in transform.py from CAMS PM2.5/PM10 via CPCB breakpoints.

-- 1) Latest reading per city, worst first  (the dashboard's city table)
SELECT r.city, r.state, r.ts_ist, r.aqi, r.category, r.pm25, r.pm10, r.dominant
FROM readings r
JOIN (SELECT city, MAX(ts_ist) AS mx FROM readings GROUP BY city) t
  ON t.city = r.city AND t.mx = r.ts_ist
ORDER BY r.aqi DESC;

-- 2) Daily AQI per city from daily-mean concentrations is computed in the
--    dashboard builder; this is the hourly-indicative daily picture:
SELECT date, city, ROUND(AVG(aqi)) AS avg_aqi, MAX(aqi) AS peak_aqi,
       ROUND(AVG(pm25), 1) AS avg_pm25
FROM readings
GROUP BY date, city
ORDER BY date, avg_aqi DESC;

-- 3) The pre-Diwali build-up: average AQI, baseline week vs the last 3 days
SELECT CASE WHEN date <= '2026-10-31' THEN 'baseline (Oct 25-31)'
            ELSE 'build-up (Nov 1+)' END AS period,
       city, ROUND(AVG(aqi)) AS avg_aqi
FROM readings
GROUP BY period, city
ORDER BY city, period;

-- 4) Worst single hours in the record
SELECT city, ts_ist, aqi, category, pm25, pm10
FROM readings
ORDER BY aqi DESC
LIMIT 10;

-- 5) Category distribution — share of city-hours in each band
SELECT category, COUNT(*) AS city_hours,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM readings), 1) AS pct
FROM readings
GROUP BY category
ORDER BY MIN(aqi);

-- 6) Diwali countdown table (filled in fully after 8 Nov):
--    Diwali day (2026-11-08) vs the same cities' October baseline
SELECT date, ROUND(AVG(aqi)) AS india_avg_aqi, MAX(aqi) AS india_peak_aqi
FROM readings
GROUP BY date
ORDER BY date;

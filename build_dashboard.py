"""
DASHBOARD step — Live AQI Dashboard (Real-Time Diwali Air Data).

Reads the SQLite store (data/aqi.db) and renders one self-contained
HTML page into site/index.html in a clean, minimalist dark style:

  * a drone-crossing-the-clouds hero over a Diwali skyline,
  * a featured-city panel (Bilaspur — the city from the owner's
    reference screenshots) with a giant AQI numeral, category, an
    Indian-scale bar (0-500) with a position marker, and PM cards,
  * the featured city's last-24-hours bar chart with min/max chips,
  * every city ranked worst -> cleanest with semicircle gauges and a
    "PM2.5 = Nx the WHO 24-h guideline" note,
  * the pre-Diwali build-up (daily AQI from daily-mean concentrations).

Every number comes from SQL at build time. CAMS also returns forecast
hours for later today; "right now" sections only use hours that have
actually arrived (<= current IST hour).

Run:  python build_dashboard.py   (after load.py)
"""

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract import CITIES  # noqa: E402
from transform import category_for, indian_aqi  # noqa: E402

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "aqi.db"
OUT_PATH = BASE / "site" / "index.html"

DIWALI = date(2026, 11, 8)  # Lakshmi Puja, Sunday 8 Nov 2026 (Drik Panchang)
FEATURED = "Bilaspur"
WHO_PM25_24H = 15.0  # µg/m³, WHO 2021 24-hour guideline

CAT_COLORS = {
    "Good": "#2ecc71", "Satisfactory": "#a3cb38", "Moderate": "#f1c40f",
    "Poor": "#e67e22", "Very Poor": "#e74c3c", "Severe": "#c0392b",
}
BANDS = [(0, 50, "Good"), (51, 100, "Satisfactory"), (101, 200, "Moderate"),
         (201, 300, "Poor"), (301, 400, "Very Poor"), (401, 500, "Severe")]
ARC_LEN = 106.8  # semicircle r=34: pi * r


SCRIPT_TEMPLATE = """
<script>
const DATA = __DATA__;
const CAT_COLORS = {"Good":"#2ecc71","Satisfactory":"#a3cb38","Moderate":"#f1c40f","Poor":"#e67e22","Very Poor":"#e74c3c","Severe":"#c0392b"};
const PM25_BANDS = [[0,30,0,50],[31,60,51,100],[61,90,101,200],[91,120,201,300],[121,250,301,400],[251,380,401,500]];
const PM10_BANDS = [[0,50,0,50],[51,100,51,100],[101,200,101,200],[201,300,201,300],[301,400,301,400],[401,500,401,500]];
function subIndex(c, bands){ if(c == null || isNaN(c)) return NaN;
  for(const b of bands){ if(c <= b[1]) return b[2] + (c - b[0]) * (b[3] - b[2]) / (b[1] - b[0]); } return 500; }
function aqiFrom(pm25, pm10){ const a = subIndex(pm25, PM25_BANDS), b = subIndex(pm10, PM10_BANDS);
  if(isNaN(a) && isNaN(b)) return [null, ""];
  if(isNaN(b) || (!isNaN(a) && a >= b)) return [Math.round(a), "PM2.5"];
  return [Math.round(b), "PM10"]; }
function catFor(a){ if(a == null) return ""; if(a <= 50) return "Good"; if(a <= 100) return "Satisfactory";
  if(a <= 200) return "Moderate"; if(a <= 300) return "Poor"; if(a <= 400) return "Very Poor"; return "Severe"; }
function pcard(name, val, sub){ const col = CAT_COLORS[catFor(sub)] || "#888";
  return '<div class="pcard" style="border-left-color:' + col + '"><div class="pcard-name">' + name +
         '</div><div class="pcard-val">' + Math.round(val) + ' <span>µg/m³</span></div></div>'; }
function renderFeatured(city, state, latest, last24, note){
  document.getElementById('featCity').textContent = city;
  document.getElementById('featState').textContent = state;
  document.getElementById('featUpdated').textContent = String(latest.ts).replace('T', ' ');
  const num = document.getElementById('featNum');
  num.textContent = latest.aqi; num.style.color = CAT_COLORS[latest.category] || '#fff';
  const cat = document.getElementById('featCat');
  cat.textContent = latest.category; cat.style.background = CAT_COLORS[latest.category] || '#333';
  document.getElementById('featDom').textContent = latest.dominant;
  document.getElementById('featNote').textContent = note || '';
  document.getElementById('marker').style.left =
    (Math.max(0, Math.min(latest.aqi, 500)) / 500 * 100).toFixed(1) + '%';
  document.getElementById('pcards').innerHTML =
    pcard('PM2.5', latest.pm25, subIndex(latest.pm25, PM25_BANDS)) +
    pcard('PM10', latest.pm10, subIndex(latest.pm10, PM10_BANDS));
  document.getElementById('chartTitle').textContent = city + ' — last 24 hours';
  let bars = '', mn = null, mx = null;
  for(const r of last24){
    if(!mn || r.aqi < mn.aqi) mn = r;
    if(!mx || r.aqi > mx.aqi) mx = r;
    bars += '<div class="hb" title="' + r.ts + ' — AQI ' + r.aqi + '"><div class="hb-fill" style="height:' +
            Math.max(2, r.aqi / 500 * 100) + '%;background:' + (CAT_COLORS[r.category] || '#888') +
            '"></div><div class="hb-t">' + String(r.ts).slice(11, 13) + '</div></div>';
  }
  document.getElementById('histBars').innerHTML = bars;
  if(mn && mx){
    document.getElementById('minmax').innerHTML =
      '<div class="minmax"><div class="mm-box" style="background:' + (CAT_COLORS[mn.category] || '#888') + '">' + mn.aqi +
      '</div><div><div class="mm-k">↓ Min AQI</div><div class="mm-t">' + String(mn.ts).slice(5) + '</div></div></div>' +
      '<div class="minmax"><div class="mm-box" style="background:' + (CAT_COLORS[mx.category] || '#888') + '">' + mx.aqi +
      '</div><div><div class="mm-k">↑ Max AQI</div><div class="mm-t">' + String(mx.ts).slice(5) + '</div></div></div>';
  }
}
function selectCity(name){ const d = DATA[name]; if(!d) return;
  renderFeatured(name, d.state, d.latest, d.last24, '');
  document.getElementById('locStatus').textContent = ''; }
document.getElementById('citySel').addEventListener('change', function(e){ selectCity(e.target.value); });
function haversine(lat1, lon1, lat2, lon2){ const R = 6371, t = Math.PI / 180;
  const dLat = (lat2 - lat1) * t, dLon = (lon2 - lon1) * t;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * t) * Math.cos(lat2 * t) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a)); }
async function useMyLocation(){
  const status = document.getElementById('locStatus'), btn = document.getElementById('locBtn');
  if(!navigator.geolocation){ status.textContent = 'Geolocation is not supported in this browser.'; return; }
  btn.disabled = true; status.textContent = 'Locating…';
  navigator.geolocation.getCurrentPosition(async function(pos){
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    let best = null, bestKm = 1e9;
    for(const name in DATA){ const d = DATA[name]; if(d.lat == null) continue;
      const km = haversine(lat, lon, d.lat, d.lon); if(km < bestKm){ bestKm = km; best = name; } }
    if(best && bestKm <= 75){
      document.getElementById('citySel').value = best; selectCity(best);
      status.textContent = 'Nearest tracked city: ' + best + ' (' + Math.round(bestKm) + ' km away).';
      btn.disabled = false; return;
    }
    status.textContent = 'No tracked city nearby — fetching live air data for your exact spot…';
    try {
      const url = 'https://air-quality-api.open-meteo.com/v1/air-quality?latitude=' + lat +
                  '&longitude=' + lon + '&hourly=pm2_5,pm10&current=pm2_5,pm10' +
                  '&past_days=1&forecast_days=0&timezone=auto';
      const res = await fetch(url); const j = await res.json();
      const cur = j.current, pair = aqiFrom(cur.pm2_5, cur.pm10);
      const latest = {ts: cur.time, aqi: pair[0], category: catFor(pair[0]),
                      pm25: cur.pm2_5, pm10: cur.pm10, dominant: pair[1]};
      const rows = [], H = j.hourly;
      for(let i = 0; i < H.time.length; i++){
        if(H.time[i] <= cur.time && H.pm2_5[i] != null && H.pm10[i] != null){
          const a2 = aqiFrom(H.pm2_5[i], H.pm10[i])[0];
          rows.push({ts: H.time[i], aqi: a2, category: catFor(a2),
                     pm25: H.pm2_5[i], pm10: H.pm10[i]});
        }
      }
      renderFeatured('Your area', 'live from your location', latest, rows.slice(-24),
        ' · fetched live from CAMS for your exact coordinates (not a tracked city; nearest tracked: ' +
        best + ', ' + Math.round(bestKm) + ' km)');
      status.textContent = 'Showing your exact location, live.';
    } catch(e) {
      status.textContent = 'Live fetch failed — showing ' + (best || 'Bilaspur') + ' instead.';
      if(best){ document.getElementById('citySel').value = best; selectCity(best); }
    }
    btn.disabled = false;
  }, function(){
    status.textContent = 'Location permission was not granted — pick your city from the list instead.';
    btn.disabled = false;
  }, {timeout: 10000});
}
document.getElementById('locBtn').addEventListener('click', useMyLocation);
</script>
</body>
</html>
"""


def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def gauge(aqi: int, category: str) -> str:
    frac = max(0.0, min(aqi, 500)) / 500.0
    color = CAT_COLORS.get(category, "#888")
    return (
        f'<svg class="gauge" viewBox="0 0 84 48">'
        f'<path d="M8 44 A34 34 0 0 1 76 44" fill="none" stroke="#2a2c33" '
        f'stroke-width="7" stroke-linecap="round"/>'
        f'<path d="M8 44 A34 34 0 0 1 76 44" fill="none" stroke="{color}" '
        f'stroke-width="7" stroke-linecap="round" '
        f'stroke-dasharray="{frac * ARC_LEN:.1f} {ARC_LEN}"/>'
        f'<text x="42" y="41" text-anchor="middle" class="gauge-num">{aqi}</text>'
        f'</svg>')


def main() -> int:
    if not DB_PATH.exists():
        print("aqi.db not found — run load.py first.")
        return 1
    now_cap = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
               ).strftime("%Y-%m-%d %H:00")
    conn = sqlite3.connect(DB_PATH)
    try:
        latest = q(conn, """
            SELECT r.city, r.state, r.ts_ist, r.aqi, r.category, r.pm25, r.pm10, r.dominant
            FROM readings r
            JOIN (SELECT city, MAX(ts_ist) AS mx FROM readings
                  WHERE ts_ist <= ? GROUP BY city) t
              ON t.city = r.city AND t.mx = r.ts_ist
            ORDER BY r.aqi DESC""", (now_cap,))
        last24 = q(conn, """
            SELECT ts_ist, aqi, category, pm25, pm10 FROM readings
            WHERE city = ? AND ts_ist <= ?
            ORDER BY ts_ist DESC LIMIT 24""", (FEATURED, now_cap))
        daily_pm = q(conn,
            "SELECT date, city, AVG(pm25), AVG(pm10) FROM readings "
            "GROUP BY date, city ORDER BY date")
        first, last, total = q(conn,
            "SELECT MIN(ts_ist), MAX(ts_ist), COUNT(*) FROM readings")[0]
        # Per-city payload for the in-page location features: every tracked
        # city's latest reading + last 24 arrived hours go into the page as
        # JSON, so the featured panel can switch to the visitor's own area
        # (nearest tracked city) without a backend.
        coords = {name: (lat, lon) for name, _, lat, lon in CITIES}
        cities_data = {}
        for row in latest:
            cname = row[0]
            rows24 = q(conn, """
                SELECT ts_ist, aqi, category, pm25, pm10 FROM readings
                WHERE city = ? AND ts_ist <= ?
                ORDER BY ts_ist DESC LIMIT 24""", (cname, now_cap))
            lat, lon = coords.get(cname, (None, None))
            cities_data[cname] = {
                "state": row[1], "lat": lat, "lon": lon,
                "latest": {"ts": row[2], "aqi": row[3], "category": row[4],
                           "pm25": row[5], "pm10": row[6], "dominant": row[7]},
                "last24": [{"ts": t, "aqi": a, "category": c, "pm25": p25,
                            "pm10": p10}
                           for t, a, c, p25, p10 in reversed(rows24)],
            }
    finally:
        conn.close()
    cities_json = json.dumps(cities_data)

    last24 = list(reversed(last24))
    feat = next((r for r in latest if r[0] == FEATURED), latest[0])
    f_city, f_state, f_ts, f_aqi, f_cat, f_pm25, f_pm10, _ = feat
    india_now = round(sum(r[3] for r in latest) / len(latest))
    india_now_cat = category_for(india_now)

    # Daily AQI from daily-mean concentrations (official-style method)
    india_daily: dict[str, list] = {}
    delhi_daily: list[tuple] = []
    for d, city, m25, m10 in daily_pm:
        aqi, _ = indian_aqi(m25, m10)
        india_daily.setdefault(d, []).append(aqi)
        if city == "Delhi":
            delhi_daily.append((d, aqi))
    india_series = [(d, round(sum(v) / len(v)))
                    for d, v in sorted(india_daily.items())]

    delta = (DIWALI - date.today()).days
    if delta > 0:
        countdown = (f"🪔 <b>{delta} days to Diwali</b> — Lakshmi Puja, Sun 8 Nov 2026 "
                     f"(Delhi muhurat 5:54–7:50 PM IST). The build-up, tracked live.")
    elif delta == 0:
        countdown = "🪔 <b>Diwali is tonight!</b> Lakshmi Puja muhurat (Delhi) 5:54–7:50 PM IST."
    else:
        countdown = f"🪔 Diwali was <b>{-delta} days ago</b> — the recovery watch."

    # --- featured panel pieces -------------------------------------------
    marker_pct = max(0.0, min(f_aqi, 500)) / 500.0 * 100
    seg_html = "".join(
        f'<div class="seg" style="left:{lo / 5}%;width:{(hi - lo) / 5}%;'
        f'background:{CAT_COLORS[name]}"></div>' for lo, hi, name in BANDS)
    band_labels = "".join(
        f'<span style="left:{lo / 5}%">{lo}</span>' for lo, _, _ in BANDS) + \
        '<span style="right:0">500</span>'

    def pollutant_card(name, value, sub_aqi):
        color = CAT_COLORS.get(category_for(sub_aqi), "#888")
        return (f'<div class="pcard" style="border-left-color:{color}">'
                f'<div class="pcard-name">{name}</div>'
                f'<div class="pcard-val">{value:.0f} <span>µg/m³</span></div></div>')

    from transform import sub_index, PM25_BANDS, PM10_BANDS
    pcards = (pollutant_card("PM2.5", f_pm25, sub_index(f_pm25, PM25_BANDS))
              + pollutant_card("PM10", f_pm10, sub_index(f_pm10, PM10_BANDS)))

    # --- last-24h chart ----------------------------------------------------
    if last24:
        mn = min(last24, key=lambda r: r[1])
        mx = max(last24, key=lambda r: r[1])
        bars = "".join(
            f'<div class="hb" title="{esc(ts)} — AQI {a}">'
            f'<div class="hb-fill" style="height:{max(2, a / 500 * 100):.0f}%;'
            f'background:{CAT_COLORS.get(cat, "#888")}"></div>'
            f'<div class="hb-t">{ts[11:13]}</div></div>'
            for ts, a, cat, _, _ in last24)
        chips = (
            f'<div class="minmax"><div class="mm-box" style="background:'
            f'{CAT_COLORS.get(mn[2], "#888")}">{mn[1]}</div><div>'
            f'<div class="mm-k">↓ Min AQI</div><div class="mm-t">{esc(mn[0][5:])}</div>'
            f'</div></div>'
            f'<div class="minmax"><div class="mm-box" style="background:'
            f'{CAT_COLORS.get(mx[2], "#888")}">{mx[1]}</div><div>'
            f'<div class="mm-k">↑ Max AQI</div><div class="mm-t">{esc(mx[0][5:])}</div>'
            f'</div></div>')
    else:
        bars, chips = "<p class='muted'>No readings yet.</p>", ""

    # --- ranking -----------------------------------------------------------
    rank_rows = ""
    for i, (c, s, ts, a, cat, p25, p10, dom) in enumerate(latest, 1):
        mult = p25 / WHO_PM25_24H
        rank_rows += (
            f'<div class="rank"><div class="rank-n">{i}</div>'
            f'<div class="rank-main"><div class="rank-city">{esc(c)}'
            f'<span class="muted">, {esc(s)}</span></div>'
            f'<div class="rank-sub">{gauge(a, cat)}'
            f'<span class="rank-cat" style="color:{CAT_COLORS.get(cat, "#888")}">'
            f'{esc(cat)}</span>'
            f'<span class="muted">PM2.5 {p25:.0f} µg/m³ · '
            f'<b class="mult">{mult:.0f}×</b> the WHO 24-h guideline</span>'
            f'</div></div></div>')

    # --- build-up bars -----------------------------------------------------
    def bars_h(series, color=None):
        peak = max(a for _, a in series) or 1
        out = ""
        for d, a in series:
            c = color or CAT_COLORS.get(category_for(a), "#888")
            out += (f'<div class="bar-row"><span class="bar-label">{d[5:]}</span>'
                    f'<div class="bar-track"><div class="bar" style="width:'
                    f'{max(3, round(a / peak * 100))}%;background:{c}"></div></div>'
                    f'<span class="bar-num">{a} · {esc(category_for(a))}</span></div>')
        return out

    options_html = "".join(
        f'<option value="{esc(c)}"{" selected" if c == FEATURED else ""}>'
        f'{esc(c)}</option>' for c in cities_data)
    built = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live AQI Dashboard — Real-Time Diwali Air Data</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
         background:#0e0f13; color:#f2f2f2; padding:26px 16px 44px; }}
  .wrap {{ max-width:860px; margin:0 auto; }}
  .muted {{ color:#9aa0a6; font-weight:normal; }}
  .hero {{ position:relative; height:210px; border-radius:14px; overflow:hidden;
          border:1px solid #26272e; margin-bottom:14px;
          background:linear-gradient(180deg,#2b1a20 0%,#452420 45%,#6e3d20 78%,#17181d 100%); }}
  .hero .glow {{ position:absolute; width:320px; height:320px; border-radius:50%;
                right:8%; top:-140px; opacity:.45; filter:blur(10px); }}
  .cloud {{ position:absolute; border-radius:50%; filter:blur(15px);
           background:radial-gradient(ellipse at center, rgba(255,240,214,.8), rgba(255,240,214,0) 70%);
           animation:drift 26s ease-in-out infinite alternate; }}
  .c1 {{ width:320px; height:66px; top:22px; left:-60px; opacity:.5; }}
  .c2 {{ width:400px; height:80px; top:56px; left:34%; opacity:.36; animation-duration:34s; }}
  .c3 {{ width:280px; height:58px; top:10px; right:-40px; opacity:.45; animation-duration:22s; }}
  .cfront {{ width:440px; height:86px; top:86px; left:16%; opacity:.3; z-index:4;
            animation-duration:30s; }}
  @keyframes drift {{ from {{ transform:translateX(-22px); }} to {{ transform:translateX(42px); }} }}
  .drone {{ position:absolute; top:54px; left:-90px; width:70px; z-index:3;
           animation:fly 13s linear infinite; }}
  @keyframes fly {{ 0% {{ transform:translate(0,0); }} 22% {{ transform:translate(30vw,-13px); }}
                   48% {{ transform:translate(56vw,7px); }} 74% {{ transform:translate(82vw,-9px); }}
                   100% {{ transform:translate(112vw,3px); }} }}
  .drone .rotor {{ transform-box:fill-box; transform-origin:center;
                  animation:spin .28s linear infinite; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  .skyline {{ position:absolute; left:0; right:0; bottom:0; height:56px; z-index:2; }}
  .hero-text {{ position:absolute; left:20px; bottom:14px; z-index:5;
               text-shadow:0 2px 10px rgba(0,0,0,.7); }}
  .hero-text h1 {{ font-size:26px; font-weight:700; letter-spacing:.2px; }}
  .hero-text h1 .accent {{ color:#f6b73c; }}
  .hero-text .sub {{ color:#e9d9ae; font-size:13.5px; margin-top:3px; }}
  .count {{ color:#c9cdd4; font-size:14px; margin:2px 2px 18px; }}
  .count b {{ color:#f6b73c; }}
  .controls {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
              margin-bottom:16px; font-size:14px; }}
  .controls select {{ background:#1e2026; color:#f2f2f2; border:1px solid #34363f;
                     border-radius:8px; padding:7px 10px; font-size:14px; }}
  .controls button {{ background:#f6b73c; color:#101114; border:none; cursor:pointer;
                     border-radius:8px; padding:8px 14px; font-size:14px;
                     font-weight:700; }}
  .controls button:disabled {{ opacity:.55; cursor:default; }}
  section {{ background:#17181d; border:1px solid #26272e; border-radius:14px;
            padding:20px; margin-bottom:14px; }}
  h2 {{ font-size:16px; font-weight:600; margin-bottom:14px; }}
  .feat-top {{ display:flex; justify-content:space-between; align-items:flex-start;
              flex-wrap:wrap; gap:8px; }}
  .live-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%;
              background:#e74c3c; margin-right:7px; animation:pulse 1.6s infinite; }}
  @keyframes pulse {{ 0% {{ opacity:1; }} 50% {{ opacity:.35; }} 100% {{ opacity:1; }} }}
  .feat-city {{ font-size:15px; color:#9aa0a6; }}
  .feat-city b {{ color:#f2f2f2; font-size:16px; }}
  .feat-big {{ display:flex; align-items:baseline; gap:16px; margin:8px 0 2px; }}
  .feat-num {{ font-size:84px; font-weight:800; line-height:1; }}
  .feat-cat {{ font-size:19px; font-weight:700; padding:7px 16px; border-radius:10px; }}
  .scale {{ position:relative; height:12px; border-radius:6px; margin:26px 0 22px;
           background:#22242b; }}
  .seg {{ position:absolute; top:0; height:12px; }}
  .seg:first-child {{ border-radius:6px 0 0 6px; }}
  .marker {{ position:absolute; top:-6px; width:22px; height:22px; border-radius:50%;
            background:#fff; border:4px solid #0e0f13; transform:translateX(-50%);
            box-shadow:0 0 0 2px #fff; }}
  .scale-labels {{ position:relative; height:16px; font-size:11.5px; color:#9aa0a6; }}
  .scale-labels span {{ position:absolute; transform:translateX(-50%); }}
  .pcards {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; }}
  .pcard {{ background:#1e2026; border-radius:10px; padding:14px 16px;
           border-left:5px solid #888; }}
  .pcard-name {{ color:#9aa0a6; font-size:13.5px; }}
  .pcard-val {{ font-size:27px; font-weight:700; margin-top:3px; }}
  .pcard-val span {{ font-size:14px; color:#9aa0a6; font-weight:400; }}
  .hist {{ display:flex; align-items:flex-end; gap:3px; height:150px; margin-top:6px; }}
  .hb {{ flex:1; display:flex; flex-direction:column; justify-content:flex-end;
        height:100%; }}
  .hb-fill {{ border-radius:3px 3px 0 0; min-height:3px; }}
  .hb-t {{ font-size:10px; color:#7c828c; text-align:center; margin-top:5px; }}
  .minmaxes {{ display:flex; gap:12px; margin-top:16px; flex-wrap:wrap; }}
  .minmax {{ flex:1; min-width:200px; display:flex; gap:12px; align-items:center;
            background:#1e2026; border-radius:10px; padding:12px 14px; }}
  .mm-box {{ min-width:56px; text-align:center; font-size:21px; font-weight:800;
            padding:9px 6px; border-radius:9px; color:#101114; }}
  .mm-k {{ font-size:13.5px; font-weight:600; }}
  .mm-t {{ font-size:12.5px; color:#9aa0a6; margin-top:2px; }}
  .rank {{ display:flex; align-items:center; gap:14px; padding:12px 2px;
          border-bottom:1px solid #22242b; }}
  .rank:last-child {{ border-bottom:none; }}
  .rank-n {{ width:22px; color:#9aa0a6; font-size:14px; }}
  .rank-main {{ flex:1; }}
  .rank-city {{ font-size:16.5px; font-weight:600; }}
  .rank-sub {{ display:flex; align-items:center; gap:12px; margin-top:2px;
              font-size:13px; flex-wrap:wrap; }}
  .gauge {{ width:74px; height:42px; }}
  .gauge-num {{ fill:#f2f2f2; font-size:16px; font-weight:700;
               font-family:inherit; }}
  .rank-cat {{ font-weight:700; font-size:14.5px; }}
  .mult {{ color:#f2f2f2; }}
  .bar-row {{ display:flex; align-items:center; gap:10px; margin:7px 0; font-size:13px; }}
  .bar-label {{ width:48px; color:#c9cdd4; flex:none; }}
  .bar-track {{ flex:1; background:#22242b; border-radius:5px; height:14px; }}
  .bar {{ height:14px; border-radius:5px; }}
  .bar-num {{ width:150px; flex:none; color:#9aa0a6; }}
  footer {{ color:#7c828c; font-size:12.5px; line-height:1.65; padding:4px 2px; }}
  a {{ color:#f6b73c; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="glow" style="background:radial-gradient(circle, {CAT_COLORS.get(india_now_cat, '#f6b73c')}, rgba(0,0,0,0) 70%)"></div>
    <div class="cloud c1"></div><div class="cloud c2"></div><div class="cloud c3"></div>
    <svg class="drone" viewBox="0 0 100 60" aria-hidden="true">
      <g stroke="#101114" fill="#101114">
        <line x1="50" y1="30" x2="16" y2="14" stroke-width="4"/>
        <line x1="50" y1="30" x2="84" y2="14" stroke-width="4"/>
        <line x1="50" y1="34" x2="20" y2="48" stroke-width="4"/>
        <line x1="50" y1="34" x2="80" y2="48" stroke-width="4"/>
        <rect x="38" y="24" width="24" height="13" rx="6"/>
        <circle cx="50" cy="40" r="3.2" fill="#f6b73c" stroke="none"/>
      </g>
      <g fill="none" stroke="#101114" stroke-width="2.4">
        <circle class="rotor" cx="16" cy="12" r="9" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="84" cy="12" r="9" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="20" cy="50" r="8" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="80" cy="50" r="8" stroke-dasharray="5 4"/>
      </g>
    </svg>
    <div class="cloud cfront"></div>
    <svg class="skyline" viewBox="0 0 880 64" preserveAspectRatio="none" aria-hidden="true">
      <path fill="#0b0c10" d="M0,64 L0,38 L46,38 L46,22 L84,22 L84,44 L128,44 L128,14 L150,14 L150,30 L196,30 L196,46 L238,46 L238,26 L286,26 L286,40 L330,40 L330,10 L356,10 L356,34 L404,34 L404,48 L452,48 L452,20 L498,20 L498,42 L540,42 L540,28 L588,28 L588,44 L632,44 L632,16 L658,16 L658,36 L706,36 L706,48 L752,48 L752,24 L800,24 L800,40 L846,40 L846,30 L880,30 L880,64 Z"/>
      <g fill="#f6b73c" opacity=".85">
        <rect x="136" y="20" width="4" height="5"/><rect x="144" y="20" width="4" height="5"/>
        <rect x="338" y="17" width="4" height="5"/><rect x="346" y="26" width="4" height="5"/>
        <rect x="462" y="27" width="4" height="5"/><rect x="640" y="23" width="4" height="5"/>
        <rect x="762" y="30" width="4" height="5"/><rect x="56" y="27" width="4" height="5"/>
        <rect x="248" y="32" width="4" height="5"/><rect x="548" y="34" width="4" height="5"/>
      </g>
    </svg>
    <div class="hero-text">
      <h1>🪔 Live <span class="accent">AQI</span> Dashboard</h1>
      <p class="sub">Real-Time Diwali Air Data · {len(latest)} Indian cities · {total} hourly readings · generated {built}</p>
    </div>
  </div>
  <p class="count">{countdown}</p>

  <section>
    <div class="controls">
      <label for="citySel">📍 Your area:</label>
      <select id="citySel">{options_html}</select>
      <button id="locBtn" type="button">Use my location</button>
      <span id="locStatus" class="muted"></span>
    </div>
    <div class="feat-top">
      <div class="feat-city"><span class="live-dot"></span>Live AQI — <b id="featCity">{esc(f_city)}</b>, <span id="featState">{esc(f_state)}</span></div>
      <div class="muted" style="font-size:13px">Updated <span id="featUpdated">{esc(f_ts)}</span> IST</div>
    </div>
    <div class="feat-big">
      <div class="feat-num" id="featNum" style="color:{CAT_COLORS.get(f_cat, '#fff')}">{f_aqi}</div>
      <div class="feat-cat" id="featCat" style="background:{CAT_COLORS.get(f_cat, '#333')};color:#101114">{esc(f_cat)}</div>
    </div>
    <div class="muted" style="font-size:13px">Indian AQI (CPCB scale) · dominant pollutant <span id="featDom">{esc(feat[7])}</span><span id="featNote"></span></div>
    <div class="scale">{seg_html}<div class="marker" id="marker" style="left:{marker_pct:.1f}%"></div></div>
    <div class="scale-labels">{band_labels}</div>
    <div class="pcards" id="pcards">{pcards}</div>
  </section>

  <section>
    <h2 id="chartTitle">{esc(f_city)} — last 24 hours</h2>
    <div class="hist" id="histBars">{bars}</div>
    <div class="minmaxes" id="minmax">{chips}</div>
  </section>

  <section>
    <h2>Live ranking — worst to cleanest</h2>
    {rank_rows}
  </section>

  <section>
    <h2>📈 The pre-Diwali build-up — all-India daily AQI</h2>
    {bars_h(india_series)}
    <h2 style="margin-top:18px">Delhi daily AQI</h2>
    {bars_h(delhi_daily)}
  </section>

  <footer>
    Method, stated plainly: concentrations are CAMS modelled data via the Open-Meteo
    Air Quality API (not ground-station readings — modelled values run smoother than a
    street-level CPCB station). Indian AQI is computed from PM2.5/PM10 with the CPCB
    breakpoint formula; hourly values are indicative, daily values use daily-mean
    concentrations like the official method. "× the WHO guideline" compares PM2.5 with
    the WHO 2021 24-hour guideline of 15 µg/m³. Window: {esc(first)} → {esc(last)} IST.
    Pipeline: API extract → pandas + quality checks → SQLite idempotent upserts → SQL → this page.
    Code: <a href="https://github.com/dxhanjay/live-aqi-dashboard">github.com/dxhanjay/live-aqi-dashboard</a>
  </footer>
</div>
"""
    html += SCRIPT_TEMPLATE.replace("__DATA__", cities_json)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard written: site/{OUT_PATH.name} ({len(html)} bytes)")
    print(f"Featured {f_city}: AQI {f_aqi} ({f_cat}) | India avg {india_now} | "
          f"worst {latest[0][0]} {latest[0][3]} | {total} readings")
    return 0


if __name__ == "__main__":
    sys.exit(main())

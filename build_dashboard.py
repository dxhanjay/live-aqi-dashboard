"""
DASHBOARD step — Live AQI Dashboard (Real-Time Diwali Air Data).

Reads the SQLite store (data/aqi.db) and renders one self-contained,
Diwali-themed HTML page into site/index.html. Every number comes from a
SQL query at build time; daily AQI figures are computed from daily-mean
PM concentrations with the same CPCB breakpoint function as the hourly
transform (closer to the official method than averaging hourly AQIs).

Run:  python build_dashboard.py   (after load.py)
"""

import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from transform import category_for, indian_aqi  # noqa: E402

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "aqi.db"
OUT_PATH = BASE / "site" / "index.html"

DIWALI = date(2026, 11, 8)  # Lakshmi Puja, Sunday 8 Nov 2026 (Drik Panchang)

CAT_COLORS = {
    "Good": "#2ecc71", "Satisfactory": "#a3cb38", "Moderate": "#f1c40f",
    "Poor": "#e67e22", "Very Poor": "#e74c3c", "Severe": "#a93226",
}
DARK_TEXT = {"Good", "Satisfactory", "Moderate"}


def q(conn, sql, args=()):
    return conn.execute(sql, args).fetchall()


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def chip(category: str, aqi) -> str:
    color = CAT_COLORS.get(category, "#888")
    fg = "#1a1206" if category in DARK_TEXT else "#ffffff"
    return (f'<span class="chip" style="background:{color};color:{fg}">'
            f'{aqi} · {esc(category)}</span>')


def main() -> int:
    if not DB_PATH.exists():
        print("aqi.db not found — run load.py first.")
        return 1
    conn = sqlite3.connect(DB_PATH)
    try:
        # CAMS includes forecast hours for later today; "right now" must only
        # use hours that have actually arrived (<= current IST hour).
        from datetime import timedelta
        now_cap = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
                   ).strftime("%Y-%m-%d %H:00")
        latest = q(conn, """
            SELECT r.city, r.state, r.ts_ist, r.aqi, r.category, r.pm25, r.pm10, r.dominant
            FROM readings r
            JOIN (SELECT city, MAX(ts_ist) AS mx FROM readings
                  WHERE ts_ist <= ? GROUP BY city) t
              ON t.city = r.city AND t.mx = r.ts_ist
            ORDER BY r.aqi DESC""", (now_cap,))
        worst_hours = q(conn,
            "SELECT city, ts_ist, aqi, category, pm25, pm10 FROM readings "
            "ORDER BY aqi DESC LIMIT 5")
        daily_pm = q(conn,
            "SELECT date, city, AVG(pm25), AVG(pm10) FROM readings "
            "GROUP BY date, city ORDER BY date")
        first, last, total = q(conn,
            "SELECT MIN(ts_ist), MAX(ts_ist), COUNT(*) FROM readings")[0]
    finally:
        conn.close()

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

    worst, cleanest = latest[0], latest[-1]
    india_now = round(sum(r[3] for r in latest) / len(latest))
    india_now_cat = category_for(india_now)

    today = date.today()
    delta = (DIWALI - today).days
    if delta > 0:
        countdown = (f"🪔 <b>{delta} day{'s' if delta != 1 else ''} to Diwali</b> — "
                     f"Lakshmi Puja, Sun 8 Nov 2026 (Delhi muhurat 5:54–7:50 PM IST). "
                     f"Watch the build-up, live.")
    elif delta == 0:
        countdown = "🪔 <b>Diwali is tonight!</b> Lakshmi Puja muhurat (Delhi) 5:54–7:50 PM IST."
    else:
        countdown = (f"🪔 Diwali was <b>{-delta} day{'s' if delta != -1 else ''} ago</b> — "
                     f"this is now the recovery watch.")

    city_rows = "\n".join(
        f"<tr><td><b>{esc(c)}</b><span class='muted'>, {esc(s)}</span></td>"
        f"<td>{chip(cat, a)}</td><td>{p25:.0f}</td><td>{p10:.0f}</td>"
        f"<td>{esc(dom)}</td><td class='muted'>{esc(ts[5:])}</td></tr>"
        for c, s, ts, a, cat, p25, p10, dom in latest)

    def bars(series, color="#f6b73c"):
        mx = max(a for _, a in series) or 1
        return "\n".join(
            f'<div class="bar-row"><span class="bar-label">{d[5:]}</span>'
            f'<div class="bar-track"><div class="bar" style="width:'
            f'{max(3, round(a / mx * 100))}%;background:{color}"></div></div>'
            f'<span class="bar-num">{a} · {esc(category_for(a))}</span></div>'
            for d, a in series)

    worst_rows = "\n".join(
        f"<tr><td><b>{esc(c)}</b></td><td>{esc(ts)}</td><td>{chip(cat, a)}</td>"
        f"<td>{p25:.0f}</td><td>{p10:.0f}</td></tr>"
        for c, ts, a, cat, p25, p10 in worst_hours)
    built = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Live AQI Dashboard — Real-Time Diwali Air Data</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; background:#160809;
         color:#f3e9d2; padding:32px 18px 48px; }}
  .wrap {{ max-width:880px; margin:0 auto; }}
  h1 {{ font-size:31px; letter-spacing:.4px; }}
  h1 .accent {{ color:#f6b73c; }}
  .sub {{ color:#c9a86a; margin:6px 0 4px; font-size:16px; }}
  .count {{ color:#e8dcc0; margin:2px 0 24px; font-size:15px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
           gap:12px; margin-bottom:26px; }}
  .card {{ background:#241114; border:1px solid #453026; border-radius:10px; padding:16px; }}
  .card .v {{ font-size:29px; color:#f6b73c; }}
  .card .k {{ color:#c9a86a; font-size:13px; margin-top:4px; }}
  .card .d {{ font-size:13px; margin-top:6px; color:#e0d3ae; }}
  section {{ background:#241114; border:1px solid #453026; border-radius:10px;
            padding:20px; margin-bottom:18px; }}
  h2 {{ font-size:18px; margin-bottom:14px; color:#f8eed3; }}
  .chip {{ display:inline-block; padding:2px 10px; border-radius:20px;
          font-size:13px; font-weight:bold; white-space:nowrap; }}
  .bar-row {{ display:flex; align-items:center; gap:10px; margin:7px 0; font-size:13px; }}
  .bar-label {{ width:52px; color:#e0d3ae; flex:none; }}
  .bar-track {{ flex:1; background:#38222a; border-radius:5px; height:16px; }}
  .bar {{ height:16px; border-radius:5px; }}
  .bar-num {{ width:150px; flex:none; color:#c9a86a; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  td, th {{ padding:7px 8px; border-bottom:1px solid #38222a; text-align:left; }}
  th {{ color:#c9a86a; font-weight:normal; font-size:12px;
       text-transform:uppercase; letter-spacing:.06em; }}
  .muted {{ color:#a68d5f; font-size:12.5px; }}
  footer {{ color:#8a7350; font-size:13px; line-height:1.6; }}
  a {{ color:#f6b73c; }}
  /* --- opening hero: a drone crosses the clouds over a Diwali skyline --- */
  .hero {{ position:relative; height:238px; border-radius:12px; overflow:hidden;
          border:1px solid #453026; margin-bottom:22px;
          background:linear-gradient(180deg,#3a1c22 0%,#57281f 42%,#8a4a24 74%,#241114 100%); }}
  .hero .glow {{ position:absolute; width:340px; height:340px; border-radius:50%;
                right:8%; top:-130px; opacity:.5; filter:blur(10px); }}
  .cloud {{ position:absolute; border-radius:50%; filter:blur(16px);
           background:radial-gradient(ellipse at center, rgba(255,240,214,.85), rgba(255,240,214,0) 70%);
           animation:drift 26s ease-in-out infinite alternate; }}
  .c1 {{ width:340px; height:74px; top:26px; left:-60px; opacity:.55; }}
  .c2 {{ width:420px; height:88px; top:64px; left:34%; opacity:.4; animation-duration:34s; }}
  .c3 {{ width:300px; height:64px; top:12px; right:-40px; opacity:.5; animation-duration:22s; }}
  .cfront {{ width:460px; height:96px; top:96px; left:16%; opacity:.34; z-index:4;
            animation-duration:30s; }}
  @keyframes drift {{ from {{ transform:translateX(-24px); }} to {{ transform:translateX(46px); }} }}
  .drone {{ position:absolute; top:64px; left:-90px; width:76px; z-index:3;
           animation:fly 13s linear infinite; }}
  @keyframes fly {{ 0% {{ transform:translate(0,0); }} 22% {{ transform:translate(30vw,-14px); }}
                   48% {{ transform:translate(56vw,8px); }} 74% {{ transform:translate(82vw,-10px); }}
                   100% {{ transform:translate(112vw,4px); }} }}
  .drone .rotor {{ transform-box:fill-box; transform-origin:center;
                  animation:spin .28s linear infinite; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  .drone .body {{ animation:bob 1.6s ease-in-out infinite alternate; }}
  @keyframes bob {{ from {{ transform:translateY(0); }} to {{ transform:translateY(3px); }} }}
  .skyline {{ position:absolute; left:0; right:0; bottom:0; height:64px; z-index:2; }}
  .haze {{ position:absolute; left:0; right:0; bottom:52px; height:56px; z-index:1;
          background:linear-gradient(180deg, rgba(246,183,60,0), rgba(246,183,60,.20)); }}
  .hero-text {{ position:absolute; left:22px; bottom:16px; z-index:5;
               text-shadow:0 2px 10px rgba(0,0,0,.65); }}
  .hero-text h1 {{ font-size:30px; }}
  .hero-text .sub {{ margin:3px 0 0; color:#f0d9a0; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="glow" style="background:radial-gradient(circle, {CAT_COLORS.get(india_now_cat, '#f6b73c')}, rgba(0,0,0,0) 70%)"></div>
    <div class="cloud c1"></div><div class="cloud c2"></div><div class="cloud c3"></div>
    <div class="haze"></div>
    <svg class="drone" viewBox="0 0 100 60" aria-hidden="true">
      <g class="body" stroke="#160809" fill="#160809">
        <line x1="50" y1="30" x2="16" y2="14" stroke-width="4"/>
        <line x1="50" y1="30" x2="84" y2="14" stroke-width="4"/>
        <line x1="50" y1="34" x2="20" y2="48" stroke-width="4"/>
        <line x1="50" y1="34" x2="80" y2="48" stroke-width="4"/>
        <rect x="38" y="24" width="24" height="13" rx="6"/>
        <circle cx="50" cy="40" r="3.2" fill="#f6b73c" stroke="none"/>
      </g>
      <g fill="none" stroke="#160809" stroke-width="2.4">
        <circle class="rotor" cx="16" cy="12" r="9" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="84" cy="12" r="9" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="20" cy="50" r="8" stroke-dasharray="5 4"/>
        <circle class="rotor" cx="80" cy="50" r="8" stroke-dasharray="5 4"/>
      </g>
    </svg>
    <div class="cloud cfront"></div>
    <svg class="skyline" viewBox="0 0 880 64" preserveAspectRatio="none" aria-hidden="true">
      <path fill="#12060a" d="M0,64 L0,38 L46,38 L46,22 L84,22 L84,44 L128,44 L128,14 L150,14 L150,30 L196,30 L196,46 L238,46 L238,26 L286,26 L286,40 L330,40 L330,10 L356,10 L356,34 L404,34 L404,48 L452,48 L452,20 L498,20 L498,42 L540,42 L540,28 L588,28 L588,44 L632,44 L632,16 L658,16 L658,36 L706,36 L706,48 L752,48 L752,24 L800,24 L800,40 L846,40 L846,30 L880,30 L880,64 Z"/>
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
      <p class="sub">Real-Time Diwali Air Data — 11 Indian cities · {esc(first)} → {esc(last)} IST ·
         {total} hourly readings · dashboard generated {built}</p>
    </div>
  </div>
  <p class="count">{countdown}</p>

  <div class="cards">
    <div class="card"><div class="v">{worst[3]}</div><div class="k">worst city right now</div>
      <div class="d">{esc(worst[0])} — {esc(worst[4])} (PM2.5 {worst[5]:.0f} µg/m³)</div></div>
    <div class="card"><div class="v">{cleanest[3]}</div><div class="k">cleanest city right now</div>
      <div class="d">{esc(cleanest[0])} — {esc(cleanest[4])} (PM2.5 {cleanest[5]:.0f} µg/m³)</div></div>
    <div class="card"><div class="v">{india_now}</div><div class="k">India average (latest)</div>
      <div class="d">{esc(india_now_cat)} across {len(latest)} cities</div></div>
    <div class="card"><div class="v">{'🪔 ' + str(delta) if delta > 0 else '🪔'}</div><div class="k">{'days to Diwali (8 Nov)' if delta > 0 else 'Diwali · 8 Nov 2026'}</div>
      <div class="d">the festival spike, tracked as it happens</div></div>
  </div>

  <section><h2>City air right now (latest reading per city)</h2>
    <table><tr><th>City</th><th>AQI</th><th>PM2.5</th><th>PM10</th><th>Dominant</th><th>Updated (IST)</th></tr>
    {city_rows}</table></section>

  <section><h2>📈 The pre-Diwali build-up — all-India daily AQI</h2>{bars(india_series)}</section>
  <section><h2>Delhi daily AQI</h2>{bars(delhi_daily, color="#e67e22")}</section>

  <section><h2>Worst single hours in the record</h2>
    <table><tr><th>City</th><th>When (IST)</th><th>AQI</th><th>PM2.5</th><th>PM10</th></tr>
    {worst_rows}</table></section>

  <footer>
    Method, stated plainly: concentrations are CAMS modelled data via the Open-Meteo
    Air Quality API (not ground-station readings); Indian AQI is computed from
    PM2.5/PM10 with the CPCB breakpoint formula — hourly values are indicative,
    daily values use daily-mean concentrations like the official method.
    Pipeline: API extract → pandas + quality checks → SQLite idempotent upserts → SQL → this page.
    Code: <a href="https://github.com/dxhanjay/live-aqi-dashboard">github.com/dxhanjay/live-aqi-dashboard</a>
  </footer>
</div>
</body>
</html>
"""
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard written: site/{OUT_PATH.name} ({len(html)} bytes)")
    print(f"Stats: {total} readings | worst now {worst[0]} {worst[3]} | "
          f"cleanest {cleanest[0]} {cleanest[3]} | India avg {india_now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

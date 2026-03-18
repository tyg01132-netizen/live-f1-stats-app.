from flask import Flask, render_template, jsonify, request
import requests
from datetime import datetime, timezone
import time
import threading

app = Flask(__name__)

CURRENT_YEAR = 2026
MIN_YEAR     = 1950
MAX_YEAR     = 2026

BASE = "https://api.jolpi.ca/ergast/f1"

# ── Simple in-memory cache ────────────────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()

# TTL per path type (seconds)
# Standings/results change at most once per race weekend → cache 5 min
# Calendar barely changes → cache 30 min
# Live data → cache 20 sec
def _cache_ttl(path):
    p = path.lower()
    if any(k in p for k in ["live", "weather", "position", "interval", "race_control"]):
        return 20
    if any(k in p for k in ["current/next", "current/last"]):
        return 60          # next/last race: 1 min
    if any(k in p for k in ["standings", "results", "qualifying", "sprint"]):
        return 300         # standings & results: 5 min
    if "races" in p or "calendar" in p:
        return 1800        # calendar: 30 min
    return 300             # default: 5 min

def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() < entry["expires"]:
            return entry["data"]
        return None

def _cache_set(key, data, ttl):
    with _cache_lock:
        _cache[key] = {"data": data, "expires": time.time() + ttl}

def jolpica(path, limit=100):
    cache_key = f"jolpica:{path}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"[cache] HIT {path}")
        return cached
    url = f"{BASE}/{path}"
    try:
        r = requests.get(url, params={"limit": limit}, timeout=5)
        print(f"[jolpica] {r.status_code} {r.url}")
        if r.status_code == 200:
            data = r.json()
            _cache_set(cache_key, data, _cache_ttl(path))
            return data
    except Exception as e:
        print(f"[jolpica] EXC {path}: {e}")
    return {}

def openf1(endpoint, params=None):
    cache_key = f"openf1:{endpoint}:{sorted((params or {}).items())}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        r = requests.get(f"https://api.openf1.org/v1/{endpoint}",
                         params=params or {}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache_set(cache_key, data, _cache_ttl(endpoint))
            return data
    except Exception as e:
        print(f"[openf1] {endpoint}: {e}")
    return []

def toint(v, d=0):
    try: return int(v)
    except: return d

def tofloat(v, d=0.0):
    try: return float(v)
    except: return d

def req_year(default=None):
    raw = request.args.get("year", default or CURRENT_YEAR)
    try: y = int(raw); return max(MIN_YEAR, min(MAX_YEAR, y))
    except: return CURRENT_YEAR

def standings_path(year, kind):
    return f"current/{kind}" if year == CURRENT_YEAR else f"{year}/{kind}"

# ── Page routes ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", year=CURRENT_YEAR)

@app.route("/calendar")
def calendar_page():
    return render_template("calendar.html", year=CURRENT_YEAR)

@app.route("/race/<int:year>/<int:round_num>")
def race_page(year, round_num):
    return render_template("race.html", year=year, round_num=round_num)

@app.route("/history")
def history():
    return render_template("history.html", min_year=MIN_YEAR, max_year=MAX_YEAR-1)

@app.route("/live")
def live_page():
    return render_template("live.html", year=CURRENT_YEAR)

@app.route("/f2")
def f2_page():
    return render_template("f2.html")

@app.route("/info")
def info_page():
    return render_template("info.html", year=CURRENT_YEAR)

# ── API: Homepage bundle (parallel fetch — fast!) ─────────────────────────────
@app.route("/api/homepage")
def api_homepage():
    """Single endpoint that returns all homepage data in one parallel request."""
    import concurrent.futures

    def fetch_next():
        try:
            data = jolpica("current/next")
            races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if not races: return {}
            r = races[0]
            sessions = {}
            for key in ["FirstPractice","SecondPractice","ThirdPractice","Qualifying","Sprint","SprintQualifying"]:
                if key in r:
                    sd = r[key].get("date",""); st = r[key].get("time","").replace("Z","")
                    sessions[key] = {"date": sd, "time": st, "iso": f"{sd}T{st}Z" if sd and st else ""}
            rd = r.get("date",""); rt = r.get("time","").replace("Z","")
            return {
                "round": r.get("round",""), "name": r.get("raceName",""),
                "circuit": r["Circuit"]["circuitName"],
                "circuit_id": r["Circuit"].get("circuitId",""),
                "country": r["Circuit"]["Location"]["country"],
                "locality": r["Circuit"]["Location"]["locality"],
                "lat": tofloat(r["Circuit"]["Location"].get("lat",0)),
                "lng": tofloat(r["Circuit"]["Location"].get("long",0)),
                "date": rd, "time": rt,
                "iso": f"{rd}T{rt}Z" if rd and rt else "",
                "sessions": sessions,
            }
        except: return {}

    def fetch_last():
        try:
            data = jolpica("current/last/results")
            races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            if not races: return {}
            race = races[0]
            results = []
            for r in race.get("Results",[])[:10]:
                d = r["Driver"]; c = r["Constructor"]
                results.append({
                    "position": r.get("position",""),
                    "driver_id": d.get("driverId",""),
                    "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                    "team": c.get("name",""), "team_id": c.get("constructorId",""),
                    "time": r.get("Time",{}).get("time", r.get("status","")),
                    "points": r.get("points",""),
                })
            race_date_str = race.get("date","")
            hours_since = 0
            if race_date_str:
                try:
                    rd = datetime.strptime(race_date_str, "%Y-%m-%d")
                    hours_since = (datetime.utcnow() - rd).total_seconds() / 3600
                except: pass
            return {
                "results_pending": hours_since < 48 and not any(r.get("position")=="1" for r in results),
                "name": race.get("raceName",""), "date": race.get("date",""),
                "season": race.get("season", CURRENT_YEAR), "round": race.get("round",""),
                "circuit": race["Circuit"]["circuitName"],
                "circuit_id": race["Circuit"].get("circuitId",""),
                "country": race["Circuit"]["Location"]["country"],
                "results": results,
            }
        except: return {}

    def fetch_drivers():
        try:
            data = jolpica(standings_path(CURRENT_YEAR, "driverstandings"))
            lists = data.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
            if not lists: return []
            out = []
            for s in lists[0].get("DriverStandings",[]):
                d = s["Driver"]; c = (s.get("Constructors") or [{}])[0]
                out.append({
                    "position": toint(s.get("position",0)),
                    "points": tofloat(s.get("points",0)),
                    "wins": toint(s.get("wins",0)),
                    "driver_id": d.get("driverId",""),
                    "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                    "code": d.get("code") or d.get("driverId","xxx")[:3].upper(),
                    "nationality": d.get("nationality",""),
                    "team": c.get("name",""), "team_id": c.get("constructorId",""),
                })
            return out
        except: return []

    def fetch_constructors():
        try:
            data = jolpica(standings_path(CURRENT_YEAR, "constructorstandings"))
            lists = data.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
            if not lists: return []
            out = []
            for s in lists[0].get("ConstructorStandings",[]):
                c = s["Constructor"]
                out.append({
                    "position": toint(s.get("position",0)),
                    "points": tofloat(s.get("points",0)),
                    "wins": toint(s.get("wins",0)),
                    "name": c.get("name",""), "team_id": c.get("constructorId",""),
                })
            return out
        except: return []

    def fetch_calendar():
        try:
            data = jolpica(standings_path(CURRENT_YEAR, "races"))
            races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            if not races:
                data = jolpica(f"{CURRENT_YEAR}/races")
                races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            now_utc = datetime.utcnow()
            out = []
            for r in races:
                try:
                    d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                    race_time = r.get("time","").replace("Z","")
                    if race_time:
                        try:
                            from datetime import timedelta
                            race_dt = datetime.strptime(f"{r['date']}T{race_time}", "%Y-%m-%dT%H:%M:%S")
                            is_past = race_dt + timedelta(hours=4) < now_utc
                        except: is_past = d < now_utc.date()
                    else:
                        is_past = d < now_utc.date()
                    out.append({
                        "round": toint(r["round"]), "name": r.get("raceName",""),
                        "circuit": r["Circuit"]["circuitName"],
                        "circuit_id": r["Circuit"].get("circuitId",""),
                        "country": r["Circuit"]["Location"]["country"],
                        "locality": r["Circuit"]["Location"]["locality"],
                        "date": r["date"], "time": race_time,
                        "iso": f"{r['date']}T{race_time}Z" if race_time else "",
                        "past": is_past, "year": CURRENT_YEAR,
                    })
                except: pass
            # Inject cancelled races
            for c in CANCELLED_2026:
                if not any(x.get("circuit_id") == c["circuit_id"] for x in out):
                    out.append(c)
            out.sort(key=lambda x: x.get("date",""))
            return out
        except: return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        f_next  = ex.submit(fetch_next)
        f_last  = ex.submit(fetch_last)
        f_drv   = ex.submit(fetch_drivers)
        f_con   = ex.submit(fetch_constructors)
        f_cal   = ex.submit(fetch_calendar)
        next_race   = f_next.result()
        last_race   = f_last.result()
        drivers     = f_drv.result()
        constructors= f_con.result()
        calendar    = f_cal.result()

    return jsonify({
        "next_race": next_race,
        "last_race": last_race,
        "driver_standings": drivers,
        "constructor_standings": constructors,
        "calendar": calendar,
    })

# ── API: Cache clear (handig voor development) ─────────────────────────────────
@app.route("/api/cache/clear")
def api_cache_clear():
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
    return jsonify({"cleared": count})

@app.route("/api/calendar")
def api_calendar():
    try:
        year = req_year()
        data = jolpica(standings_path(year, "races"))
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races and year == CURRENT_YEAR:
            data = jolpica(f"{year}/races")
            races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        now_utc = datetime.utcnow()
        out = []
        for r in races:
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                race_time = r.get("time","").replace("Z","")
                # Build full race datetime for accurate past check
                # Add 4 hours grace period for race finish + cool-down lap
                if race_time:
                    try:
                        race_dt = datetime.strptime(f"{r['date']}T{race_time}", "%Y-%m-%dT%H:%M:%S")
                        # Race is "past" 4h after scheduled start (roughly race finish time)
                        from datetime import timedelta
                        is_past = race_dt + timedelta(hours=4) < now_utc
                    except:
                        is_past = d < now_utc.date()
                else:
                    # No time info: treat as past if date has passed (using end of day UTC+14 = most eastern timezone)
                    is_past = d < now_utc.date()

                def sess_dt(key):
                    s = r.get(key, {})
                    if not s: return {}
                    sd = s.get("date","")
                    st = s.get("time","").replace("Z","")
                    return {"date": sd, "time": st, "iso": f"{sd}T{st}Z" if sd and st else ""}

                out.append({
                    "round":      toint(r["round"]),
                    "name":       r.get("raceName",""),
                    "circuit":    r["Circuit"]["circuitName"],
                    "circuit_id": r["Circuit"].get("circuitId",""),
                    "country":    r["Circuit"]["Location"]["country"],
                    "locality":   r["Circuit"]["Location"]["locality"],
                    "lat":        tofloat(r["Circuit"]["Location"].get("lat",0)),
                    "lng":        tofloat(r["Circuit"]["Location"].get("long",0)),
                    "date":       r["date"],
                    "time":       race_time,
                    "iso":        f"{r['date']}T{race_time}Z" if race_time else "",
                    "past":       is_past,
                    "year":       year,
                    "sessions": {
                        "fp1":    sess_dt("FirstPractice"),
                        "fp2":    sess_dt("SecondPractice"),
                        "fp3":    sess_dt("ThirdPractice"),
                        "quali":  sess_dt("Qualifying"),
                        "sprint": sess_dt("Sprint"),
                        "sprint_quali": sess_dt("SprintQualifying"),
                    },
                    # legacy flat fields
                    "fp1":   r.get("FirstPractice",{}).get("date",""),
                    "fp2":   r.get("SecondPractice",{}).get("date",""),
                    "fp3":   r.get("ThirdPractice",{}).get("date",""),
                    "quali": r.get("Qualifying",{}).get("date",""),
                    "sprint":r.get("Sprint",{}).get("date",""),
                })
            except Exception as e:
                print(f"[calendar] row: {e}")
        # Inject cancelled 2026 races if applicable
        if year == 2026:
            for c in CANCELLED_2026:
                if not any(r.get("circuit_id") == c["circuit_id"] for r in out):
                    out.append(c)
            out.sort(key=lambda r: r.get("date", ""))
        return jsonify(out)
    except Exception as e:
        print(f"[calendar] ERR: {e}")
        return jsonify([])

# ── API: Standings ────────────────────────────────────────────────────────────
@app.route("/api/standings/drivers")
def api_driver_standings():
    try:
        year = req_year()
        data = jolpica(standings_path(year, "driverstandings"))
        lists = data.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        if not lists: return jsonify([])
        out = []
        for s in lists[0].get("DriverStandings",[]):
            d = s["Driver"]; c = (s.get("Constructors") or [{}])[0]
            out.append({
                "position":    toint(s.get("position",0)),
                "points":      tofloat(s.get("points",0)),
                "wins":        toint(s.get("wins",0)),
                "driver_id":   d.get("driverId",""),
                "name":        f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "code":        d.get("code") or d.get("driverId","xxx")[:3].upper(),
                "number":      d.get("permanentNumber",""),
                "nationality": d.get("nationality",""),
                "team":        c.get("name",""),
                "team_id":     c.get("constructorId",""),
            })
        return jsonify(out)
    except Exception as e:
        print(f"[standings/d] ERR: {e}")
        return jsonify([])

@app.route("/api/standings/constructors")
def api_constructor_standings():
    try:
        year = req_year()
        data = jolpica(standings_path(year, "constructorstandings"))
        lists = data.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        if not lists: return jsonify([])
        out = []
        for s in lists[0].get("ConstructorStandings",[]):
            c = s["Constructor"]
            out.append({
                "position":    toint(s.get("position",0)),
                "points":      tofloat(s.get("points",0)),
                "wins":        toint(s.get("wins",0)),
                "name":        c.get("name",""),
                "team_id":     c.get("constructorId",""),
                "nationality": c.get("nationality",""),
            })
        return jsonify(out)
    except Exception as e:
        print(f"[standings/c] ERR: {e}")
        return jsonify([])

# ── API: Championship progression (points per round) ─────────────────────────
@app.route("/api/progression/<int:year>")
def api_progression(year):
    try:
        # Get all race results for the season to compute cumulative points
        data = jolpica(f"{year}/results", limit=1000)
        races_raw = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        driver_points = {}  # driver_id -> [pts_after_round_1, pts_after_round_2, ...]
        round_names = []
        cumulative = {}

        for race in sorted(races_raw, key=lambda x: toint(x["round"])):
            round_names.append(race["raceName"].replace("Grand Prix","GP"))
            for result in race.get("Results",[]):
                did = result["Driver"]["driverId"]
                name = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                pts = tofloat(result.get("points",0))
                tid = (result.get("Constructor") or {}).get("constructorId","")
                if did not in cumulative:
                    cumulative[did] = {"name": name, "team_id": tid, "pts": 0.0, "series": []}
                cumulative[did]["pts"] += pts
                cumulative[did]["series"].append(cumulative[did]["pts"])

        # Pad shorter series with last value
        max_len = len(round_names)
        for did, info in cumulative.items():
            while len(info["series"]) < max_len:
                info["series"].append(info["pts"])

        # Sort by final points, take top 10
        sorted_drivers = sorted(cumulative.items(), key=lambda x: -x[1]["pts"])[:10]
        return jsonify({
            "rounds": round_names,
            "drivers": [{"id": did, "name": v["name"], "team_id": v["team_id"], "series": v["series"]}
                        for did, v in sorted_drivers]
        })
    except Exception as e:
        print(f"[progression] ERR: {e}")
        return jsonify({"rounds":[], "drivers":[]})

# ── API: Race results ─────────────────────────────────────────────────────────
@app.route("/api/results/<int:year>/<int:round_num>")
def api_results(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/results")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify({"race":None,"results":[]})
        race = races[0]
        info = {
            "name":       race.get("raceName",""),
            "date":       race.get("date",""),
            "season":     race.get("season", year),
            "round":      race.get("round", round_num),
            "circuit":    race["Circuit"]["circuitName"],
            "circuit_id": race["Circuit"].get("circuitId",""),
            "country":    race["Circuit"]["Location"]["country"],
            "locality":   race["Circuit"]["Location"]["locality"],
        }
        results = []
        for r in race.get("Results",[]):
            d = r["Driver"]; c = r["Constructor"]
            results.append({
                "position":     r.get("position",""),
                "grid":         r.get("grid",""),
                "driver_id":    d.get("driverId",""),
                "name":         f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "code":         d.get("code",""),
                "number":       d.get("permanentNumber",""),
                "team":         c.get("name",""),
                "team_id":      c.get("constructorId",""),
                "laps":         r.get("laps",""),
                "status":       r.get("status",""),
                "points":       r.get("points",""),
                "time":         r.get("Time",{}).get("time", r.get("status","")),
                "fastest_lap":  r.get("FastestLap",{}).get("Time",{}).get("time",""),
                "fastest_rank": r.get("FastestLap",{}).get("rank",""),
            })
        return jsonify({"race": info, "results": results})
    except Exception as e:
        print(f"[results] ERR: {e}")
        return jsonify({"race":None,"results":[]})

@app.route("/api/qualifying/<int:year>/<int:round_num>")
def api_qualifying(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/qualifying")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify([])
        out = []
        for r in races[0].get("QualifyingResults",[]):
            d = r["Driver"]; c = r["Constructor"]
            out.append({
                "position": toint(r.get("position",0)),
                "driver_id": d.get("driverId",""),
                "name":     f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "code":     d.get("code",""),
                "team":     c.get("name",""), "team_id": c.get("constructorId",""),
                "q1": r.get("Q1","—"), "q2": r.get("Q2","—"), "q3": r.get("Q3","—"),
            })
        return jsonify(out)
    except Exception as e:
        print(f"[qualifying] ERR: {e}")
        return jsonify([])

@app.route("/api/pitstops/<int:year>/<int:round_num>")
def api_pitstops(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/pitstops")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify([])
        return jsonify(races[0].get("PitStops",[]))
    except Exception as e:
        return jsonify([])

@app.route("/api/last-race")
def api_last_race():
    try:
        data = jolpica("current/last/results")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify({})
        race = races[0]
        results = []
        for r in race.get("Results",[])[:10]:
            d = r["Driver"]; c = r["Constructor"]
            results.append({
                "position": r.get("position",""),
                "driver_id": d.get("driverId",""),
                "name":     f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "team":     c.get("name",""), "team_id": c.get("constructorId",""),
                "time":     r.get("Time",{}).get("time", r.get("status","")),
                "points":   r.get("points",""),
            })
        # Results are typically available from Jolpica within 1-3 days after the race
        # (usually by Monday or Tuesday). We pass a flag so the frontend can inform users.
        race_date_str = race.get("date","")
        hours_since_race = 0
        if race_date_str:
            try:
                rd = datetime.strptime(race_date_str, "%Y-%m-%d")
                hours_since_race = (datetime.utcnow() - rd).total_seconds() / 3600
            except: pass
        results_may_be_pending = hours_since_race < 48
        return jsonify({
            "results_pending": results_may_be_pending and not [r for r in results if r.get("position") == "1"],
            "name": race.get("raceName",""), "date": race.get("date",""),
            "season": race.get("season", CURRENT_YEAR), "round": race.get("round",""),
            "circuit": race["Circuit"]["circuitName"],
            "circuit_id": race["Circuit"].get("circuitId",""),
            "country": race["Circuit"]["Location"]["country"],
            "results": results,
        })
    except Exception as e:
        # Results are typically available from Jolpica within 1-3 days after the race
        # (usually by Monday or Tuesday). We pass a flag so the frontend can inform users.
        race_date_str = race.get("date","")
        hours_since_race = 0
        if race_date_str:
            try:
                rd = datetime.strptime(race_date_str, "%Y-%m-%d")
                hours_since_race = (datetime.utcnow() - rd).total_seconds() / 3600
            except: pass
        results_may_be_pending = hours_since_race < 48
        return jsonify({
            "results_pending": results_may_be_pending and not [r for r in results if r.get("position") == "1"],})

@app.route("/api/next-race")
def api_next_race():
    try:
        data = jolpica("current/next")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify({})
        r = races[0]
        sessions = {}
        for key in ["FirstPractice","SecondPractice","ThirdPractice","Qualifying","Sprint","SprintQualifying"]:
            if key in r:
                sd = r[key].get("date",""); st = r[key].get("time","").replace("Z","")
                sessions[key] = {"date": sd, "time": st, "iso": f"{sd}T{st}Z" if sd and st else ""}
        rd = r.get("date",""); rt = r.get("time","").replace("Z","")
        return jsonify({
            "round": r.get("round",""), "name": r.get("raceName",""),
            "circuit": r["Circuit"]["circuitName"],
            "circuit_id": r["Circuit"].get("circuitId",""),
            "country": r["Circuit"]["Location"]["country"],
            "locality": r["Circuit"]["Location"]["locality"],
            "lat": tofloat(r["Circuit"]["Location"].get("lat",0)),
            "lng": tofloat(r["Circuit"]["Location"].get("long",0)),
            "date": rd, "time": rt,
            "iso": f"{rd}T{rt}Z" if rd and rt else "",
            "sessions": sessions,
        })
    except Exception as e:
        return jsonify({})

# ── API: History ──────────────────────────────────────────────────────────────
@app.route("/api/history/season")
def api_history_season():
    try:
        year = req_year(2025)
        year = min(year, MAX_YEAR - 1)
        cal  = jolpica(f"{year}/races")
        drv  = jolpica(f"{year}/driverstandings")
        con  = jolpica(f"{year}/constructorstandings")

        today = datetime.today().date()
        races = []
        for r in cal.get("MRData",{}).get("RaceTable",{}).get("Races",[]):
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                races.append({
                    "round": toint(r["round"]), "name": r.get("raceName",""),
                    "circuit": r["Circuit"]["circuitName"],
                    "circuit_id": r["Circuit"].get("circuitId",""),
                    "country": r["Circuit"]["Location"]["country"],
                    "locality": r["Circuit"]["Location"]["locality"],
                    "date": r["date"], "past": d < now_utc.date(), "year": year,
                })
            except: pass

        ds_lists = drv.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        driver_standings = []
        for s in (ds_lists[0].get("DriverStandings",[]) if ds_lists else []):
            d = s["Driver"]; c = (s.get("Constructors") or [{}])[0]
            driver_standings.append({
                "position": toint(s.get("position",0)),
                "points": tofloat(s.get("points",0)),
                "wins": toint(s.get("wins",0)),
                "driver_id": d.get("driverId",""),
                "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "code": d.get("code") or d.get("driverId","xxx")[:3].upper(),
                "nationality": d.get("nationality",""),
                "team": c.get("name",""), "team_id": c.get("constructorId",""),
            })

        cs_lists = con.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        constructor_standings = []
        for s in (cs_lists[0].get("ConstructorStandings",[]) if cs_lists else []):
            c = s["Constructor"]
            constructor_standings.append({
                "position": toint(s.get("position",0)),
                "points": tofloat(s.get("points",0)),
                "wins": toint(s.get("wins",0)),
                "name": c.get("name",""), "team_id": c.get("constructorId",""),
                "nationality": c.get("nationality",""),
            })

        return jsonify({
            "year": year, "races": races,
            "driver_standings": driver_standings,
            "constructor_standings": constructor_standings,
        })
    except Exception as e:
        print(f"[history] ERR: {e}")
        return jsonify({"year":0,"races":[],"driver_standings":[],"constructor_standings":[]})

# ── API: F2 via OpenF1 ────────────────────────────────────────────────────────
@app.route("/api/f2/sessions")
def api_f2_sessions():
    try:
        sessions = openf1("sessions", {"year": CURRENT_YEAR})
        f2 = [s for s in sessions if "formula 2" in s.get("series","").lower()
              or "f2" in s.get("series","").lower()
              or "formula 2" in s.get("meeting_name","").lower()]
        if not f2:
            # Try by session type
            f2 = [s for s in sessions if s.get("circuit_key") and
                  any(k in (s.get("session_name","").lower()) for k in ["feature","sprint","qualifying","practice"])
                  and s.get("meeting_key")]
        f2.sort(key=lambda x: x.get("date_start",""), reverse=True)
        return jsonify(f2[:20])
    except Exception as e:
        print(f"[f2/sessions] ERR: {e}")
        return jsonify([])

@app.route("/api/f2/standings")
def api_f2_standings():
    """Scrape F2 standings from the official API"""
    try:
        # Use the official F2/FIA timing data
        r = requests.get(
            "https://api.formula2.com/v1/fom-results/race?year=" + str(CURRENT_YEAR),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if r.status_code == 200:
            return jsonify(r.json())
    except: pass

    # Fallback: return placeholder noting F2 data source
    return jsonify({"note": "F2 standings via openf1", "available": False})

@app.route("/api/f2/calendar")
def api_f2_calendar():
    try:
        # F2 follows the same calendar as F1, get F1 calendar for event dates
        data = jolpica("current/races")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        today = datetime.today().date()
        # F2 races happen at same venues as F1
        out = []
        for r in races:
            d = datetime.strptime(r["date"],"%Y-%m-%d").date()
            out.append({
                "round": toint(r["round"]),
                "name": r.get("raceName","").replace("Grand Prix","F2"),
                "circuit": r["Circuit"]["circuitName"],
                "circuit_id": r["Circuit"].get("circuitId",""),
                "country": r["Circuit"]["Location"]["country"],
                "locality": r["Circuit"]["Location"]["locality"],
                "date": r["date"],
                "past": d < now_utc.date(),
            })
        return jsonify(out)
    except Exception as e:
        return jsonify([])

# ── API: Circuit photo ────────────────────────────────────────────────────────
WIKI = {
    "albert_park":"Albert_Park_Grand_Prix_Circuit","bahrain":"Bahrain_International_Circuit",
    "jeddah":"Jeddah_Street_Circuit","shanghai":"Shanghai_International_Circuit",
    "miami":"Miami_International_Autodrome","imola":"Autodromo_Enzo_e_Dino_Ferrari",
    "monaco":"Circuit_de_Monaco","villeneuve":"Circuit_Gilles_Villeneuve",
    "catalunya":"Circuit_de_Barcelona-Catalunya","red_bull_ring":"Red_Bull_Ring",
    "silverstone":"Silverstone_Circuit","hungaroring":"Hungaroring",
    "spa":"Circuit_de_Spa-Francorchamps","zandvoort":"Circuit_Zandvoort",
    "monza":"Autodromo_Nazionale_Monza","baku":"Baku_City_Circuit",
    "marina_bay":"Marina_Bay_Street_Circuit","suzuka":"Suzuka_International_Racing_Course",
    "losail":"Losail_International_Circuit","americas":"Circuit_of_the_Americas",
    "rodriguez":"Autodromo_Hermanos_Rodriguez","interlagos":"Autodromo_Jose_Carlos_Pace",
    "vegas":"Las_Vegas_Street_Circuit","yas_marina":"Yas_Marina_Circuit",
}

@app.route("/api/photo/<circuit_id>")
def api_photo(circuit_id):
    try:
        article = WIKI.get(circuit_id)
        if not article: return jsonify({"url":""})
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{article}",
                         headers={"User-Agent":"F1Dashboard/3.0"}, timeout=8)
        if r.status_code == 200:
            j = r.json()
            img = j.get("originalimage") or j.get("thumbnail") or {}
            return jsonify({"url": img.get("source",""), "title": j.get("title","")})
    except: pass
    return jsonify({"url":""})

# ── API: Live ─────────────────────────────────────────────────────────────────
def latest_session():
    sessions = openf1("sessions", {"year": CURRENT_YEAR})
    if not sessions: return None
    sessions.sort(key=lambda x: x.get("date_start",""), reverse=True)
    return sessions[0]

@app.route("/api/live/status")
def api_live_status():
    try:
        s = latest_session()
        if not s: return jsonify({"active":False,"reason":"Geen sessies"})
        name = s.get("session_name","").lower()
        start = s.get("date_start",""); end = s.get("date_end","")
        # Any F1 session type is shown live (practice, quali, sprint, race)
        relevant = any(k in name for k in ["race","qualifying","sprint","shootout","practice","training"])
        is_live = False
        if start:
            s_dt = datetime.fromisoformat(start.replace("Z","+00:00"))
            now  = datetime.now(timezone.utc)
            elapsed = (now - s_dt).total_seconds()
            if elapsed > 0:
                if end:
                    e_dt = datetime.fromisoformat(end.replace("Z","+00:00"))
                    hours_since_end = (now - e_dt).total_seconds() / 3600
                    is_live = hours_since_end < 0.5
                else:
                    hours = elapsed / 3600
                    # Practice=1h, Quali=1h, Race=2h, Sprint=30min
                    max_dur = 2.5 if "race" in name else 1.5
                    is_live = hours < max_dur
        return jsonify({
            "active": is_live,
            "any_session": bool(s),
            "session_key": s.get("session_key"),
            "session_name": s.get("session_name",""),
            "meeting_name": s.get("meeting_name",""),
            "circuit": s.get("circuit_short_name",""),
            "date_start": start,
            "reason": f"Laatste: {s.get('session_name','?')} ({start[:10] if start else '?'})",
        })
    except Exception as e:
        return jsonify({"active":False,"reason":str(e)})

@app.route("/api/live/timing")
def api_live_timing():
    try:
        s = latest_session()
        if not s: return jsonify([])
        sk = s.get("session_key")
        drivers = {d["driver_number"]: d for d in openf1("drivers",{"session_key":sk})}
        pos_all = openf1("position",{"session_key":sk})
        int_all = openf1("intervals",{"session_key":sk})
        lap_all = openf1("laps",{"session_key":sk})
        pos_lat = {}
        for p in pos_all:
            dn = p.get("driver_number")
            if dn and (dn not in pos_lat or p.get("date","") > pos_lat[dn].get("date","")):
                pos_lat[dn] = p
        int_lat = {}
        for i in int_all:
            dn = i.get("driver_number")
            if dn and (dn not in int_lat or i.get("date","") > int_lat[dn].get("date","")):
                int_lat[dn] = i
        lap_lat = {}
        for l in lap_all:
            dn = l.get("driver_number")
            if dn and (dn not in lap_lat or toint(l.get("lap_number",0)) > toint(lap_lat[dn].get("lap_number",0))):
                lap_lat[dn] = l
        out = []
        for dn, pos in sorted(pos_lat.items(), key=lambda x: toint(x[1].get("position",99))):
            d = drivers.get(dn,{}); iv = int_lat.get(dn,{}); lp = lap_lat.get(dn,{})
            out.append({
                "position": pos.get("position"), "driver_number": dn,
                "name": d.get("full_name",""), "code": d.get("name_acronym",""),
                "team": d.get("team_name",""), "team_colour": d.get("team_colour","555555"),
                "gap": iv.get("gap_to_leader",""), "interval": iv.get("interval",""),
                "lap_time": lp.get("lap_duration",""), "lap_number": lp.get("lap_number",""),
            })
        return jsonify(out)
    except Exception as e:
        return jsonify([])

@app.route("/api/live/weather")
def api_live_weather():
    try:
        s = latest_session()
        if not s: return jsonify({})
        data = openf1("weather",{"session_key":s.get("session_key")})
        return jsonify(data[-1] if data else {})
    except: return jsonify({})

@app.route("/api/live/messages")
def api_live_messages():
    try:
        s = latest_session()
        if not s: return jsonify([])
        data = openf1("race_control",{"session_key":s.get("session_key")})
        return jsonify(data[-20:] if len(data)>20 else data)
    except: return jsonify([])


@app.route("/api/stats/season")
def api_stats_season():
    """Comprehensive current season stats"""
    try:
        year = CURRENT_YEAR
        # Get all results for the season
        results_data = jolpica(f"{year}/results", limit=1000)
        races_raw = results_data.get("MRData",{}).get("RaceTable",{}).get("Races",[])

        total_races = len(races_raw)
        winners = {}
        pole_sitters = {}
        fastest_laps = {}
        dnfs = {}
        all_results = []

        for race in races_raw:
            for r in race.get("Results",[]):
                did = r["Driver"]["driverId"]
                name = f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
                tid = r.get("Constructor",{}).get("constructorId","")
                tname = r.get("Constructor",{}).get("name","")
                pos = toint(r.get("position",99))
                status = r.get("status","")
                
                if pos == 1:
                    winners[name] = winners.get(name, {"count":0,"team_id":tid}); winners[name]["count"]+=1
                
                fl = r.get("FastestLap",{})
                if fl.get("rank") == "1":
                    fastest_laps[name] = fastest_laps.get(name, {"count":0,"team_id":tid}); fastest_laps[name]["count"]+=1
                
                if "Retired" in status or "DNF" in status or "Accident" in status or "Collision" in status:
                    dnfs[name] = dnfs.get(name, {"count":0,"team_id":tid}); dnfs[name]["count"]+=1

        # Qualifying for poles
        quali_data = jolpica(f"current/qualifying", limit=1000)
        quali_races = quali_data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        for race in quali_races:
            results = race.get("QualifyingResults",[])
            if results:
                r = results[0]
                name = f"{r['Driver']['givenName']} {r['Driver']['familyName']}"
                tid = r.get("Constructor",{}).get("constructorId","")
                pole_sitters[name] = pole_sitters.get(name, {"count":0,"team_id":tid}); pole_sitters[name]["count"]+=1

        # Driver standings for points
        ds_data = jolpica("current/driverstandings")
        ds_lists = ds_data.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        leader_points = 0
        if ds_lists:
            standings = ds_lists[0].get("DriverStandings",[])
            if standings:
                leader_points = tofloat(standings[0].get("points",0))

        return jsonify({
            "total_races": total_races,
            "leader_points": leader_points,
            "winners": sorted([{"name":k,"count":v["count"],"team_id":v["team_id"]} for k,v in winners.items()], key=lambda x:-x["count"]),
            "pole_sitters": sorted([{"name":k,"count":v["count"],"team_id":v["team_id"]} for k,v in pole_sitters.items()], key=lambda x:-x["count"]),
            "fastest_laps": sorted([{"name":k,"count":v["count"],"team_id":v["team_id"]} for k,v in fastest_laps.items()], key=lambda x:-x["count"]),
            "dnfs": sorted([{"name":k,"count":v["count"],"team_id":v["team_id"]} for k,v in dnfs.items()], key=lambda x:-x["count"]),
        })
    except Exception as e:
        print(f"[stats] ERR: {e}")
        return jsonify({})

# ── API: Debug ────────────────────────────────────────────────────────────────
@app.route("/api/debug")
def api_debug():
    out = {}
    d1 = jolpica("current/races")
    out["calendar"] = {"races": len(d1.get("MRData",{}).get("RaceTable",{}).get("Races",[]))}
    d2 = jolpica("current/driverstandings")
    l2 = d2.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
    out["driver_standings"] = {"drivers": len(l2[0].get("DriverStandings",[]) if l2 else [])}
    d3 = jolpica(f"{CURRENT_YEAR}/1/results")
    r3 = d3.get("MRData",{}).get("RaceTable",{}).get("Races",[])
    out["race1_results"] = {"count": len(r3[0].get("Results",[]) if r3 else [])}
    try:
        pr = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/Circuit_de_Monaco",
                         headers={"User-Agent":"F1/3.0"}, timeout=5)
        out["photo_api"] = {"ok": pr.status_code==200}
    except Exception as e:
        out["photo_api"] = {"ok": False, "error": str(e)}
    return jsonify(out)

# ── New feature pages ─────────────────────────────────────────────────────────
@app.route("/stats")
def stats_page():
    return render_template("stats.html", year=CURRENT_YEAR)

@app.route("/compare")
def compare_page():
    return render_template("compare.html", year=CURRENT_YEAR)

@app.route("/map")
def map_page():
    return render_template("map.html", year=CURRENT_YEAR)

@app.route("/predictor")
def predictor_page():
    return render_template("predictor.html", year=CURRENT_YEAR)

@app.route("/timeline")
def timeline_page():
    return render_template("timeline.html", year=CURRENT_YEAR)

# ── API: Lap times ────────────────────────────────────────────────────────────
@app.route("/api/laps/<int:year>/<int:round_num>")
def api_laps(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/laps", limit=2000)
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races: return jsonify([])
        laps = races[0].get("Laps",[])
        # Restructure: {driverId: [lap1time, lap2time, ...]}
        drivers = {}
        for lap in laps:
            lap_num = toint(lap.get("number",0))
            for timing in lap.get("Timings",[]):
                did = timing.get("driverId","")
                if did not in drivers:
                    drivers[did] = {"times": [], "positions": []}
                drivers[did]["times"].append(timing.get("time",""))
                drivers[did]["positions"].append(toint(timing.get("position",0)))
        return jsonify(drivers)
    except Exception as e:
        print(f"[laps] ERR: {e}")
        return jsonify({})

# ── API: Head-to-head career comparison ──────────────────────────────────────
@app.route("/api/h2h")
def api_h2h():
    try:
        d1 = request.args.get("d1","")
        d2 = request.args.get("d2","")
        if not d1 or not d2: return jsonify({})
        # Get career stats for both drivers
        def driver_career(did):
            wins_d = jolpica(f"drivers/{did}/results?status=1", limit=500)
            all_d  = jolpica(f"drivers/{did}/results", limit=500)
            titles_d = jolpica(f"drivers/{did}/driverstandings/1", limit=100)
            races_raw = all_d.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            wins_raw  = wins_d.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            titles_raw = titles_d.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
            podiums = sum(1 for r in races_raw if toint((r.get("Results") or [{}])[0].get("position",99)) <= 3)
            points  = sum(tofloat((r.get("Results") or [{}])[0].get("points",0)) for r in races_raw)
            return {
                "id": did,
                "races": len(races_raw),
                "wins": len(wins_raw),
                "podiums": podiums,
                "points": round(points,1),
                "titles": len(titles_raw),
            }
        r1 = driver_career(d1)
        r2 = driver_career(d2)
        return jsonify({"d1": r1, "d2": r2})
    except Exception as e:
        print(f"[h2h] ERR: {e}")
        return jsonify({})

# ── API: Championship predictor ───────────────────────────────────────────────
@app.route("/api/predictor")
def api_predictor():
    try:
        # Current standings + remaining races
        cal   = jolpica("current/races")
        ds    = jolpica("current/driverstandings")
        races = cal.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        lists = ds.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        if not races or not lists: return jsonify({})

        today = datetime.today().date()
        remaining = sum(1 for r in races if datetime.strptime(r["date"],"%Y-%m-%d").date() > today)
        # Max points per race = 26 (25 + fastest lap)
        max_per_race = 26
        standings = []
        for s in lists[0].get("DriverStandings",[]):
            d = s["Driver"]; c = (s.get("Constructors") or [{}])[0]
            cur = tofloat(s.get("points",0))
            max_possible = cur + remaining * max_per_race
            standings.append({
                "driver_id": d.get("driverId",""),
                "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "team_id": c.get("constructorId",""),
                "current_points": cur,
                "max_possible": max_possible,
                "wins": toint(s.get("wins",0)),
                "position": toint(s.get("position",0)),
            })
        leader_max = standings[0]["max_possible"] if standings else 0
        for s in standings:
            s["mathematically_alive"] = s["max_possible"] >= (standings[0]["current_points"] if standings else 0)
        return jsonify({
            "standings": standings,
            "remaining_races": remaining,
            "max_per_race": max_per_race,
        })
    except Exception as e:
        print(f"[predictor] ERR: {e}")
        return jsonify({})

# ── API: Season comparison ────────────────────────────────────────────────────
@app.route("/api/compare/seasons")
def api_compare_seasons():
    try:
        y1 = toint(request.args.get("y1", CURRENT_YEAR-1))
        y2 = toint(request.args.get("y2", CURRENT_YEAR))
        def season_summary(year):
            path = "current/driverstandings" if year == CURRENT_YEAR else f"{year}/driverstandings"
            ds = jolpica(path)
            cp = jolpica("current/constructorstandings" if year == CURRENT_YEAR else f"{year}/constructorstandings")
            cal = jolpica(f"{year}/races")
            ds_lists = ds.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
            cp_lists = cp.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
            races = cal.get("MRData",{}).get("RaceTable",{}).get("Races",[])
            drivers = ds_lists[0].get("DriverStandings",[]) if ds_lists else []
            teams   = cp_lists[0].get("ConstructorStandings",[]) if cp_lists else []
            drv_champ = drivers[0] if drivers else {}
            team_champ = teams[0] if teams else {}
            d = drv_champ.get("Driver",{})
            c = team_champ.get("Constructor",{})
            return {
                "year": year, "races": len(races),
                "driver_champion": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "driver_id": d.get("driverId",""),
                "driver_points": tofloat(drv_champ.get("points",0)),
                "driver_wins": toint(drv_champ.get("wins",0)),
                "team_champion": c.get("name",""),
                "team_id": c.get("constructorId",""),
                "team_points": tofloat(team_champ.get("points",0)),
                "drivers": [{"name": f"{s['Driver'].get('givenName','')} {s['Driver'].get('familyName','')}".strip(),
                             "driver_id": s["Driver"].get("driverId",""),
                             "team_id": (s.get("Constructors") or [{}])[0].get("constructorId",""),
                             "points": tofloat(s.get("points",0)),
                             "wins": toint(s.get("wins",0))} for s in drivers[:10]],
            }
        return jsonify({"s1": season_summary(y1), "s2": season_summary(y2)})
    except Exception as e:
        print(f"[compare] ERR: {e}")
        return jsonify({})

# ── API: Sprint race results ──────────────────────────────────────────────────
@app.route("/api/sprint/<int:year>/<int:round_num>")
def api_sprint(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/sprint")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races:
            return jsonify({})
        r = races[0]
        results = []
        for res in r.get("SprintResults", []):
            d = res.get("Driver",{}); c = res.get("Constructor",{})
            results.append({
                "position":    res.get("position",""),
                "driver_id":   d.get("driverId",""),
                "number":      d.get("permanentNumber",""),
                "code":        d.get("code",""),
                "name":        f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "team":        c.get("name",""),
                "team_id":     c.get("constructorId",""),
                "grid":        res.get("grid",""),
                "laps":        res.get("laps",""),
                "status":      res.get("status",""),
                "time":        res.get("Time",{}).get("time","") if res.get("Time") else res.get("status",""),
                "points":      tofloat(res.get("points",0)),
                "fastest_lap": res.get("FastestLap",{}).get("Time",{}).get("time","") if res.get("FastestLap") else "",
                "fastest_rank": res.get("FastestLap",{}).get("rank","") if res.get("FastestLap") else "",
            })
        return jsonify({
            "name":    r.get("raceName",""),
            "date":    r.get("date",""),
            "circuit": r.get("Circuit",{}).get("circuitName",""),
            "results": results,
        })
    except Exception as e:
        print(f"[sprint] ERR: {e}")
        return jsonify({})

# ── API: Sprint qualifying ────────────────────────────────────────────────────
@app.route("/api/sprint-qualifying/<int:year>/<int:round_num>")
def api_sprint_qualifying(year, round_num):
    try:
        data = jolpica(f"{year}/{round_num}/sprintqualifying")
        races = data.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        if not races:
            return jsonify({})
        r = races[0]
        results = []
        for res in r.get("SprintQualifyingResults", r.get("QualifyingResults", [])):
            d = res.get("Driver",{}); c = res.get("Constructor",{})
            results.append({
                "position": res.get("position",""),
                "driver_id": d.get("driverId",""),
                "code":      d.get("code",""),
                "name":      f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "team":      c.get("name",""),
                "team_id":   c.get("constructorId",""),
                "q1":        res.get("Q1",""),
                "q2":        res.get("Q2",""),
                "q3":        res.get("Q3",""),
            })
        return jsonify({
            "name":    r.get("raceName",""),
            "circuit": r.get("Circuit",{}).get("circuitName",""),
            "results": results,
        })
    except Exception as e:
        print(f"[sprint-quali] ERR: {e}")
        return jsonify({})



# ── CANCELLED RACES 2026 (Bahrain & Saudi Arabia - conflict Midden-Oosten) ────
CANCELLED_2026 = [
    {
        "round": 1, "name": "Bahrein Grand Prix",
        "circuit": "Bahrain International Circuit", "circuit_id": "bahrain",
        "country": "Bahrain", "locality": "Sakhir",
        "lat": 26.032, "lng": 50.511,
        "date": "2026-04-12", "time": "15:00:00",
        "iso": "2026-04-12T15:00:00Z",
        "past": True, "year": 2026, "cancelled": True,
        "cancel_reason": "Afgelast vanwege het aanhoudende conflict in het Midden-Oosten",
        "sessions": {}
    },
    {
        "round": 2, "name": "Saoedi-Arabische Grand Prix",
        "circuit": "Jeddah Corniche Circuit", "circuit_id": "jeddah",
        "country": "Saudi Arabia", "locality": "Jeddah",
        "lat": 21.632, "lng": 39.104,
        "date": "2026-04-19", "time": "17:00:00",
        "iso": "2026-04-19T17:00:00Z",
        "past": True, "year": 2026, "cancelled": True,
        "cancel_reason": "Afgelast vanwege het aanhoudende conflict in het Midden-Oosten",
        "sessions": {}
    },
]

# ── API: Weather via wttr.in ──────────────────────────────────────────────────
CIRCUIT_CITIES = {
    "albert_park": "Melbourne", "bahrain": "Sakhir",
    "jeddah": "Jeddah", "shanghai": "Shanghai",
    "miami": "Miami", "imola": "Imola",
    "monaco": "Monaco", "villeneuve": "Montreal",
    "catalunya": "Barcelona", "red_bull_ring": "Spielberg",
    "silverstone": "Silverstone", "hungaroring": "Budapest",
    "spa": "Spa", "zandvoort": "Zandvoort",
    "monza": "Monza", "baku": "Baku",
    "marina_bay": "Singapore", "suzuka": "Suzuka",
    "losail": "Lusail", "americas": "Austin",
    "rodriguez": "Mexico City", "interlagos": "Sao Paulo",
    "vegas": "Las Vegas", "yas_marina": "Abu Dhabi",
}

@app.route("/api/weather/<circuit_id>")
def api_weather(circuit_id):
    try:
        city = CIRCUIT_CITIES.get(circuit_id, circuit_id.replace("_", " ").title())
        r = requests.get(
            f"https://wttr.in/{city}?format=j1",
            headers={"User-Agent": "F1Dashboard/3.0"},
            timeout=8
        )
        if r.status_code == 200:
            d = r.json()
            cur = d.get("current_condition", [{}])[0]
            today = d.get("weather", [{}])[0]
            hourly = today.get("hourly", [])
            forecast = []
            for h in hourly:
                forecast.append({
                    "time": h.get("time", ""),
                    "temp": h.get("tempC", ""),
                    "desc": (h.get("weatherDesc") or [{}])[0].get("value", ""),
                    "rain_chance": h.get("chanceofrain", "0"),
                    "wind_kmph": h.get("windspeedKmph", ""),
                })
            return jsonify({
                "city": city,
                "temp_c": cur.get("temp_C", ""),
                "feels_like": cur.get("FeelsLikeC", ""),
                "humidity": cur.get("humidity", ""),
                "wind_kmph": cur.get("windspeedKmph", ""),
                "desc": (cur.get("weatherDesc") or [{}])[0].get("value", ""),
                "weather_code": cur.get("weatherCode", ""),
                "forecast": forecast[:8],
                "sunrise": today.get("astronomy", [{}])[0].get("sunrise", ""),
                "sunset": today.get("astronomy", [{}])[0].get("sunset", ""),
            })
    except Exception as e:
        print(f"[weather] ERR: {e}")
    return jsonify({"error": "Weerdata niet beschikbaar"})

# ── API: ICS Calendar export ──────────────────────────────────────────────────
from flask import Response
import re as _re

@app.route("/api/calendar/ics")
def api_calendar_ics():
    try:
        year = req_year()
        data = jolpica(standings_path(year, "races"))
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races and year == CURRENT_YEAR:
            data = jolpica(f"{year}/races")
            races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//F1FORLIFE//F1 Calendar//NL",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:F1 Seizoen {year}",
            "X-WR-CALDESC:Formule 1 racekalender",
            "X-WR-TIMEZONE:UTC",
        ]

        def ics_dt(date_str, time_str=""):
            ds = date_str.replace("-", "")
            if time_str:
                ts = time_str.replace(":", "").replace("Z", "")[:6]
                return f"{ds}T{ts}Z"
            return f"{ds}T120000Z"

        def ics_str(s):
            return _re.sub(r"[^\x20-\x7E]", "", s)

        for race in races:
            rd = race.get("date", ""); rt = race.get("time", "").replace("Z", "")
            cid = f"race-{year}-{race['round']}@f1forlife"
            name = ics_str(race.get("raceName", ""))
            circuit = ics_str(race["Circuit"]["circuitName"])
            country = ics_str(race["Circuit"]["Location"]["country"])
            dtstart = ics_dt(rd, rt)
            dtend_dt = datetime.strptime(rd, "%Y-%m-%d")
            dtend = ics_dt(rd, (datetime.strptime(rt, "%H:%M:%S") if rt else datetime(2000,1,1,14,0,0)).strftime("%H:%M:%S"))

            lines += [
                "BEGIN:VEVENT",
                f"UID:{cid}",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dtstart}",
                f"DTEND:{ics_dt(rd, (datetime.strptime(rt,'%H:%M:%S')+__import__('datetime').timedelta(hours=2)).strftime('%H:%M:%S') if rt else '16:00:00')}",
                f"SUMMARY:🏎 {name}",
                f"LOCATION:{circuit}, {country}",
                f"DESCRIPTION:Formule 1 Grand Prix\\nRonde {race['round']} van {year}\\nCircuit: {circuit}",
                "END:VEVENT",
            ]
            # Add qualifying session
            if "Qualifying" in race:
                qd = race["Qualifying"].get("date", ""); qt = race["Qualifying"].get("time", "").replace("Z", "")
                lines += [
                    "BEGIN:VEVENT",
                    f"UID:quali-{year}-{race['round']}@f1forlife",
                    f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                    f"DTSTART:{ics_dt(qd, qt)}",
                    f"DTEND:{ics_dt(qd, (datetime.strptime(qt,'%H:%M:%S')+__import__('datetime').timedelta(hours=1)).strftime('%H:%M:%S') if qt else '13:00:00')}",
                    f"SUMMARY:⏱ Kwalificatie — {name.replace(' Grand Prix','')}",
                    f"LOCATION:{circuit}, {country}",
                    "END:VEVENT",
                ]

        lines.append("END:VCALENDAR")
        ics_content = "\r\n".join(lines)
        return Response(
            ics_content,
            mimetype="text/calendar",
            headers={"Content-Disposition": f"attachment; filename=f1-{year}.ics"}
        )
    except Exception as e:
        print(f"[ics] ERR: {e}")
        return Response("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR", mimetype="text/calendar")

# ── API: Streaming guide ──────────────────────────────────────────────────────
@app.route("/api/streaming-guide")
def api_streaming_guide():
    guide = [
        {"country": "Nederland", "flag": "🇳🇱", "broadcaster": "Viaplay", "type": "betaal", "url": "https://viaplay.nl", "note": "Alle sessies live inclusief VT"},
        {"country": "België", "flag": "🇧🇪", "broadcaster": "Play Sports / Viaplay", "type": "betaal", "url": "https://viaplay.be", "note": "Nederlandstalig via Viaplay"},
        {"country": "Duitsland", "flag": "🇩🇪", "broadcaster": "Sky Sport F1", "type": "betaal", "url": "https://sky.de", "note": "Sky Go app beschikbaar"},
        {"country": "Verenigd Koninkrijk", "flag": "🇬🇧", "broadcaster": "Sky Sports F1", "type": "betaal", "url": "https://sky.com/sports", "note": "Gratis samenvattingen via Channel 4"},
        {"country": "Italië", "flag": "🇮🇹", "broadcaster": "Sky Italia / TV8", "type": "gemengd", "url": "https://tv8.it", "note": "TV8 gratis voor races (vertraagd)"},
        {"country": "Spanje", "flag": "🇪🇸", "broadcaster": "DAZN / Canal+", "type": "betaal", "url": "https://dazn.com", "note": "DAZN heeft live-rechten 2024+"},
        {"country": "Frankrijk", "flag": "🇫🇷", "broadcaster": "Canal+", "type": "betaal", "url": "https://canalplus.com", "note": "MyCANAL streaming app"},
        {"country": "Australië", "flag": "🇦🇺", "broadcaster": "Fox Sports / Kayo", "type": "betaal", "url": "https://kayosports.com.au", "note": "Kayo voor streaming"},
        {"country": "VS", "flag": "🇺🇸", "broadcaster": "ESPN / F1 TV Pro", "type": "gemengd", "url": "https://f1tv.formula1.com", "note": "F1 TV Pro = alle sessies live"},
        {"country": "Canada", "flag": "🇨🇦", "broadcaster": "TSN / RDS", "type": "betaal", "url": "https://tsn.ca", "note": "RDS voor Franstalig Canada"},
        {"country": "Japan", "flag": "🇯🇵", "broadcaster": "Fuji TV / DAZN", "type": "gemengd", "url": "https://dazn.com/ja-JP", "note": "Fuji TV gratis voor GP Japan"},
        {"country": "Brazilië", "flag": "🇧🇷", "broadcaster": "Globo / BandSports", "type": "gemengd", "url": "https://globo.com", "note": "Globo gratis voor races"},
        {"country": "Wereldwijd", "flag": "🌍", "broadcaster": "F1 TV Pro", "type": "betaal", "url": "https://f1tv.formula1.com", "note": "Officieel platform — alle sessies, geen commentaar in sommige landen"},
    ]
    return jsonify(guide)

# ── API: Race incident timeline (race control messages via OpenF1) ────────────
@app.route("/api/race-incidents/<int:year>/<int:round_num>")
def api_race_incidents(year, round_num):
    try:
        # Get session key for this race
        sessions = openf1("sessions", {"year": year, "session_name": "Race"})
        if not sessions:
            return jsonify([])
        # Match by round/meeting if possible
        meeting_name = ""
        cal = jolpica(f"{year}/{round_num}/races")
        races = cal.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if races:
            meeting_name = races[0].get("raceName", "").lower().replace(" grand prix", "")

        session = None
        if meeting_name:
            for s in sessions:
                if any(w in s.get("meeting_name", "").lower() for w in meeting_name.split()):
                    session = s; break
        if not session and sessions:
            # fallback: pick by date proximity
            race_date = races[0].get("date", "") if races else ""
            if race_date:
                for s in sessions:
                    if s.get("date_start", "").startswith(race_date[:7]):  # same month
                        session = s; break
            if not session:
                session = sessions[-1]

        sk = session.get("session_key")
        messages = openf1("race_control", {"session_key": sk})
        out = []
        for m in messages:
            cat = m.get("category", "")
            flag_type = m.get("flag", "")
            scope = m.get("scope", "")
            msg = m.get("message", "")
            lap = m.get("lap_number", "")
            ts = m.get("date", "")
            icon = "📋"
            if "SAFETY CAR" in msg.upper() or "SC" == flag_type: icon = "🚗"
            elif "VIRTUAL SAFETY CAR" in msg.upper() or "VSC" in msg.upper(): icon = "🟡"
            elif "RED FLAG" in msg.upper() or flag_type == "RED": icon = "🔴"
            elif "YELLOW" in flag_type: icon = "🟡"
            elif "DRS" in msg.upper(): icon = "⚡"
            elif "PENALTY" in msg.upper() or "INVESTIGATION" in msg.upper(): icon = "⚖️"
            elif "CHEQUERED" in msg.upper(): icon = "🏁"
            out.append({
                "lap": lap, "time": ts, "icon": icon,
                "message": msg, "flag": flag_type, "category": cat,
            })
        return jsonify(out)
    except Exception as e:
        print(f"[race-incidents] ERR: {e}")
        return jsonify([])

# ── API: Sector times leaderboard (via OpenF1 laps) ──────────────────────────
@app.route("/api/sector-times/<int:year>/<int:round_num>")
def api_sector_times(year, round_num):
    try:
        sessions = openf1("sessions", {"year": year, "session_name": "Race"})
        if not sessions: return jsonify([])
        cal = jolpica(f"{year}/{round_num}/races")
        races = cal.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        race_date = races[0].get("date", "") if races else ""
        session = None
        for s in sessions:
            if race_date and s.get("date_start", "").startswith(race_date[:7]):
                session = s; break
        if not session: session = sessions[-1]
        sk = session.get("session_key")

        laps = openf1("laps", {"session_key": sk})
        drivers = {d["driver_number"]: d for d in openf1("drivers", {"session_key": sk})}

        # Find best sectors per driver
        driver_bests = {}
        for lap in laps:
            dn = lap.get("driver_number")
            if not dn: continue
            s1 = lap.get("duration_sector_1")
            s2 = lap.get("duration_sector_2")
            s3 = lap.get("duration_sector_3")
            if dn not in driver_bests:
                driver_bests[dn] = {"s1": None, "s2": None, "s3": None}
            if s1 and (driver_bests[dn]["s1"] is None or s1 < driver_bests[dn]["s1"]):
                driver_bests[dn]["s1"] = s1
            if s2 and (driver_bests[dn]["s2"] is None or s2 < driver_bests[dn]["s2"]):
                driver_bests[dn]["s2"] = s2
            if s3 and (driver_bests[dn]["s3"] is None or s3 < driver_bests[dn]["s3"]):
                driver_bests[dn]["s3"] = s3

        result = []
        for dn, bests in driver_bests.items():
            d = drivers.get(dn, {})
            s1, s2, s3 = bests["s1"], bests["s2"], bests["s3"]
            total = (s1 or 0) + (s2 or 0) + (s3 or 0) if all([s1, s2, s3]) else None
            result.append({
                "driver_number": dn,
                "name": d.get("full_name", f"#{dn}"),
                "code": d.get("name_acronym", str(dn)),
                "team": d.get("team_name", ""),
                "team_colour": "#" + (d.get("team_colour") or "666666"),
                "s1": round(s1, 3) if s1 else None,
                "s2": round(s2, 3) if s2 else None,
                "s3": round(s3, 3) if s3 else None,
                "total": round(total, 3) if total else None,
            })
        result.sort(key=lambda x: x["total"] or 999)
        return jsonify(result)
    except Exception as e:
        print(f"[sector-times] ERR: {e}")
        return jsonify([])

# ── API: Speed trap data (via OpenF1 car_data) ────────────────────────────────
@app.route("/api/speed-trap/<int:year>/<int:round_num>")
def api_speed_trap(year, round_num):
    try:
        sessions = openf1("sessions", {"year": year, "session_name": "Race"})
        if not sessions: return jsonify([])
        cal = jolpica(f"{year}/{round_num}/races")
        races = cal.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        race_date = races[0].get("date", "") if races else ""
        session = None
        for s in sessions:
            if race_date and s.get("date_start", "").startswith(race_date[:7]):
                session = s; break
        if not session: session = sessions[-1]
        sk = session.get("session_key")

        drivers = {d["driver_number"]: d for d in openf1("drivers", {"session_key": sk})}
        # Use laps endpoint — has lap duration & is more compact than car_data
        laps = openf1("laps", {"session_key": sk})

        driver_max = {}
        for lap in laps:
            dn = lap.get("driver_number")
            spd = lap.get("st_speed")  # speed trap field
            if not dn or not spd: continue
            try: spd = float(spd)
            except: continue
            if dn not in driver_max or spd > driver_max[dn]["speed"]:
                driver_max[dn] = {"speed": spd, "lap": lap.get("lap_number", "")}

        result = []
        for dn, info in driver_max.items():
            d = drivers.get(dn, {})
            result.append({
                "driver_number": dn,
                "name": d.get("full_name", f"#{dn}"),
                "code": d.get("name_acronym", str(dn)),
                "team": d.get("team_name", ""),
                "team_colour": "#" + (d.get("team_colour") or "666666"),
                "speed": info["speed"],
                "lap": info["lap"],
            })
        result.sort(key=lambda x: -x["speed"])
        return jsonify(result)
    except Exception as e:
        print(f"[speed-trap] ERR: {e}")
        return jsonify([])

# ── API: Race positions per lap (replay) ──────────────────────────────────────
@app.route("/api/race-positions/<int:year>/<int:round_num>")
def api_race_positions(year, round_num):
    try:
        sessions = openf1("sessions", {"year": year, "session_name": "Race"})
        if not sessions: return jsonify({})
        cal = jolpica(f"{year}/{round_num}/races")
        races = cal.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        race_date = races[0].get("date", "") if races else ""
        session = None
        for s in sessions:
            if race_date and s.get("date_start", "").startswith(race_date[:7]):
                session = s; break
        if not session: session = sessions[-1]
        sk = session.get("session_key")

        drivers_list = openf1("drivers", {"session_key": sk})
        drivers = {d["driver_number"]: d for d in drivers_list}
        laps = openf1("laps", {"session_key": sk})

        # Build per-driver per-lap position
        by_lap = {}
        for lap in laps:
            dn = lap.get("driver_number")
            ln = lap.get("lap_number")
            pos = lap.get("position") or lap.get("lap_number")  # fallback
            if not dn or not ln: continue
            if ln not in by_lap: by_lap[ln] = {}
            by_lap[ln][dn] = lap.get("position", "")

        # Build position data per driver per lap
        max_lap = max(by_lap.keys()) if by_lap else 0
        driver_series = {}
        for dn in drivers:
            driver_series[dn] = []
            for lap_n in range(1, max_lap + 1):
                pos = by_lap.get(lap_n, {}).get(dn, None)
                driver_series[dn].append(pos)

        # Filter to drivers with actual data
        active_drivers = {dn: v for dn, v in driver_series.items() if any(v)}

        return jsonify({
            "max_lap": max_lap,
            "drivers": [
                {
                    "number": dn,
                    "name": drivers.get(dn, {}).get("full_name", f"#{dn}"),
                    "code": drivers.get(dn, {}).get("name_acronym", str(dn)),
                    "team": drivers.get(dn, {}).get("team_name", ""),
                    "colour": "#" + (drivers.get(dn, {}).get("team_colour") or "666666"),
                    "positions": v,
                }
                for dn, v in active_drivers.items()
            ]
        })
    except Exception as e:
        print(f"[race-positions] ERR: {e}")
        return jsonify({})


# ── API: Homepage weather + strategy ─────────────────────────────────────────
@app.route("/api/race-strategy/<circuit_id>")
def api_race_strategy(circuit_id):
    """Weather + tyre strategy advice for a circuit — uses race weekend forecast."""
    try:
        city = CIRCUIT_CITIES.get(circuit_id, circuit_id.replace("_"," ").title())
        # Get next race date to find the right forecast day
        race_date_str = request.args.get("race_date","")
        r = requests.get(f"https://wttr.in/{city}?format=j1",
                         headers={"User-Agent":"F1Dashboard/3.0"}, timeout=8)
        if r.status_code != 200:
            return jsonify({"error":"Weerdata niet beschikbaar"})
        d = r.json()
        # wttr.in returns 3 days: today [0], tomorrow [1], day after [2]
        # Pick the day closest to the race date
        weather_days = d.get("weather",[])
        target_day = weather_days[0] if weather_days else {}
        days_until = 0
        is_forecast = False
        if race_date_str and len(weather_days) > 1:
            try:
                race_dt = datetime.strptime(race_date_str, "%Y-%m-%d").date()
                today_dt = datetime.utcnow().date()
                days_until = (race_dt - today_dt).days
                if days_until <= 0:
                    target_day = weather_days[0]  # race already passed, use today
                elif days_until == 1 and len(weather_days) > 1:
                    target_day = weather_days[1]
                    is_forecast = True
                elif days_until >= 2 and len(weather_days) > 2:
                    target_day = weather_days[2]
                    is_forecast = True
                elif days_until > 2:
                    # Race too far away - use day 2 as best approximation
                    target_day = weather_days[-1]
                    is_forecast = True
            except: pass

        cur = d.get("current_condition",[{}])[0]
        hourly = target_day.get("hourly",[])

        # If race is more than 3 days away, wttr.in can't give accurate forecast
        if days_until > 3 and is_forecast:
            race_date_nice = race_date_str if race_date_str else "de race"
            return jsonify({
                "city": city,
                "too_far": True,
                "days_until": days_until,
                "message": f"Weersverwachting voor {city} is pas beschikbaar ~3 dagen voor de race.",
                "temp_c": int(cur.get("temp_C", 20)),
                "desc": (cur.get("weatherDesc") or [{}])[0].get("value",""),
                "weather_code": cur.get("weatherCode","113"),
                "rain_chance": 0,
                "wind_kmph": int(cur.get("windspeedKmph",0)),
                "strategies": [{
                    "icon": "📅",
                    "title": f"Race over {days_until} dagen",
                    "desc": f"Weersverwachting voor {city} verschijnt ~3 dagen voor de race. Nu huidig weer getoond.",
                    "type": "info"
                }],
                "is_forecast": False,
                "forecast": []
            })

        # Use race-day max temp, not current temp
        race_day_temps = [int(h.get("tempC", cur.get("temp_C",20))) for h in hourly]
        race_day_max = max(race_day_temps) if race_day_temps else int(cur.get("temp_C",20))

        temp = race_day_max
        humidity = int(cur.get("humidity",50))
        wind = int(max((int(h.get("windspeedKmph",0)) for h in hourly), default=int(cur.get("windspeedKmph",0))))
        rain_chance = max((int(h.get("chanceofrain",0)) for h in hourly), default=0)
        afternoon = hourly[len(hourly)//2] if hourly else {}
        code = int(afternoon.get("weatherCode", cur.get("weatherCode",113)))

        # Determine condition
        is_rain = code in [176,185,263,266,281,284,293,296,299,302,305,308,
                           311,314,317,320,356,359,362,365,374,377,386,389]
        is_cloudy = code in [116,119,122,143,248,260]
        is_sunny = code in [113]

        # Strategy advice
        strategies = []

        if rain_chance > 60 or is_rain:
            strategies.append({
                "icon": "🌧",
                "title": "Regen verwacht",
                "desc": "Intermediates of full wets bij de start. Safety car scenario waarschijnlijk — teams die laat pitten naar slicks hebben voordeel.",
                "type": "danger"
            })
            strategies.append({
                "icon": "🔄",
                "title": "Undercut kans hoog",
                "desc": "Bij wisselende omstandigheden is de pitstop-timing cruciaal. Teams reageren direct op track position na safety car.",
                "type": "info"
            })
        elif rain_chance > 30:
            strategies.append({
                "icon": "⛅",
                "title": "Kans op bui",
                "desc": "Medium als startband voor flexibiliteit. Overcut-strategie riskant — hou intermediates klaar in de pitbox.",
                "type": "warning"
            })
        
        if temp > 35:
            strategies.append({
                "icon": "🔥",
                "title": f"Hoge temperatuur ({temp}°C)",
                "desc": "Harde compounds favoriet — zachte banden degraderen snel. Verwacht 2-stop strategie bij de meeste teams.",
                "type": "danger"
            })
        elif temp < 15:
            strategies.append({
                "icon": "🥶",
                "title": f"Koude track ({temp}°C)",
                "desc": "Zachtste compound werkt beter voor opwarming. 1-stop strategie haalbaar door lagere degradatie.",
                "type": "info"
            })
        else:
            strategies.append({
                "icon": "✅",
                "title": f"Ideale omstandigheden ({temp}°C)",
                "desc": "Medium start → Hard voor 1-stop, of Soft → Medium voor agressieve undercut.",
                "type": "success"
            })

        if wind > 40:
            strategies.append({
                "icon": "💨",
                "title": f"Harde wind ({wind} km/u)",
                "desc": "Hoge downforce setup voordelig. Energie-management lastiger — ERS herlaadt minder efficient in rechte lijn.",
                "type": "warning"
            })

        # Use race-day afternoon weather description
        afternoon_desc = (afternoon.get("weatherDesc") or [{}])[0].get("value","") if afternoon else (cur.get("weatherDesc") or [{}])[0].get("value","")
        return jsonify({
            "city": city,
            "days_until": days_until,
            "is_forecast": is_forecast,
            "temp_c": temp,
            "humidity": humidity,
            "wind_kmph": wind,
            "rain_chance": rain_chance,
            "desc": afternoon_desc,
            "weather_code": code,
            "strategies": strategies,
            "forecast": [
                {
                    "time": h.get("time",""),
                    "temp": h.get("tempC",""),
                    "rain": h.get("chanceofrain","0"),
                    "wind": h.get("windspeedKmph",""),
                }
                for h in hourly[:6]
            ]
        })
    except Exception as e:
        print(f"[race-strategy] ERR: {e}")
        return jsonify({"error": "Weerdata niet beschikbaar"})

# ── Startup prefetch — warm de cache op vóór eerste bezoek ────────────────────
def _prefetch():
    """Fetches de meestgebruikte data direct bij opstarten in de achtergrond."""
    import time
    time.sleep(1)  # wacht tot Flask volledig opgestart is
    print("[prefetch] Cache warming gestart...")
    try:
        jolpica("current/next")
        print("[prefetch] ✓ next race")
    except: pass
    try:
        jolpica("current/last/results")
        print("[prefetch] ✓ last race")
    except: pass
    try:
        jolpica(standings_path(CURRENT_YEAR, "driverstandings"))
        print("[prefetch] ✓ driver standings")
    except: pass
    try:
        jolpica(standings_path(CURRENT_YEAR, "constructorstandings"))
        print("[prefetch] ✓ constructor standings")
    except: pass
    try:
        jolpica(standings_path(CURRENT_YEAR, "races"))
        print("[prefetch] ✓ calendar")
    except: pass
    print("[prefetch] ✅ Cache warm — homepage laadt nu instant!")

if __name__ == "__main__":
    # Start prefetch in achtergrond
    t = threading.Thread(target=_prefetch, daemon=True)
    t.start()
    app.run(debug=True, port=5000, host="0.0.0.0")

# ── API: Countdown widget (embeddable HTML) ────────────────────────────────────
@app.route("/widget/countdown")
def widget_countdown():
    """Embeddable countdown widget - add as iframe on any site."""
    return render_template("widget_countdown.html", year=CURRENT_YEAR)

# ── API: What-if simulator ─────────────────────────────────────────────────────
@app.route("/simulator")
def simulator_page():
    return render_template("simulator.html", year=CURRENT_YEAR)

@app.route("/api/simulator/standings")
def api_simulator_standings():
    try:
        cal = jolpica("current/races")
        ds  = jolpica("current/driverstandings")
        races = cal.get("MRData",{}).get("RaceTable",{}).get("Races",[])
        lists = ds.get("MRData",{}).get("StandingsTable",{}).get("StandingsLists",[])
        if not lists: return jsonify({})
        today = datetime.today().date()
        remaining = [r for r in races if datetime.strptime(r["date"],"%Y-%m-%d").date() > today]
        drivers = []
        for s in lists[0].get("DriverStandings",[]):
            d = s["Driver"]; c = (s.get("Constructors") or [{}])[0]
            drivers.append({
                "driver_id": d.get("driverId",""),
                "name": f"{d.get('givenName','')} {d.get('familyName','')}".strip(),
                "code": d.get("code","???"),
                "team_id": c.get("constructorId",""),
                "points": tofloat(s.get("points",0)),
                "wins": toint(s.get("wins",0)),
                "position": toint(s.get("position",0)),
            })
        return jsonify({
            "drivers": drivers,
            "remaining_races": [{"round": toint(r["round"]), "name": r.get("raceName","").replace(" Grand Prix","")} for r in remaining],
            "max_per_race": 26,
        })
    except Exception as e:
        print(f"[simulator] ERR: {e}")
        return jsonify({})

# ── SEO: sitemap.xml ──────────────────────────────────────────────────────────
@app.route("/sitemap.xml")
def sitemap():
    pages = [
        ("https://f1forlife.onrender.com/", "daily", "1.0"),
        ("https://f1forlife.onrender.com/calendar", "weekly", "0.9"),
        ("https://f1forlife.onrender.com/stats", "daily", "0.9"),
        ("https://f1forlife.onrender.com/live", "always", "0.8"),
        ("https://f1forlife.onrender.com/map", "weekly", "0.8"),
        ("https://f1forlife.onrender.com/compare", "weekly", "0.7"),
        ("https://f1forlife.onrender.com/predictor", "daily", "0.8"),
        ("https://f1forlife.onrender.com/simulator", "daily", "0.8"),
        ("https://f1forlife.onrender.com/timeline", "monthly", "0.6"),
        ("https://f1forlife.onrender.com/history", "monthly", "0.6"),
        ("https://f1forlife.onrender.com/info", "monthly", "0.7"),
        ("https://f1forlife.onrender.com/f2", "daily", "0.7"),
    ]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url, freq, prio in pages:
        xml += f"  <url><loc>{url}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>\n"
    xml += "</urlset>"
    from flask import Response
    return Response(xml, mimetype="application/xml")

# ── SEO: robots.txt ───────────────────────────────────────────────────────────
@app.route("/robots.txt")
def robots():
    txt = "User-agent: *\nAllow: /\nSitemap: https://f1forlife.onrender.com/sitemap.xml\n"
    from flask import Response
    return Response(txt, mimetype="text/plain")

@app.route("/google170879bc78331920.html")
def google_verify():
    return "google-site-verification: google170879bc78331920.html"

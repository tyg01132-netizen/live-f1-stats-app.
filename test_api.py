"""
Voer dit uit NAAST app.py om te testen welke data de APIs teruggeven.
Gebruik: python3 test_api.py
"""
import requests, json

BASE = "http://localhost:5000"

def test(name, url):
    try:
        r = requests.get(BASE + url, timeout=10)
        data = r.json()
        if isinstance(data, list):
            print(f"✅ {name}: {len(data)} items")
            if data: print(f"   Eerste: {json.dumps(data[0], ensure_ascii=False)[:120]}")
        elif isinstance(data, dict):
            print(f"✅ {name}: dict met keys {list(data.keys())[:5]}")
        else:
            print(f"❓ {name}: {data}")
    except Exception as e:
        print(f"❌ {name}: {e}")

print("=== F1 Dashboard API Test ===\n")
test("Driver standings 2026", "/api/standings/drivers?year=2026")
test("Constructor standings 2026", "/api/standings/constructors?year=2026")
test("Laatste race", "/api/last-race")
test("Volgende race", "/api/next-race")
test("Kalender 2026", "/api/calendar?year=2026")
test("Race resultaten r1", "/api/results/2026/1")
test("Live status", "/api/live/status")
test("Debug", "/api/debug")

"""
Run this once to get real circuit photo URLs from Wikipedia.
The URLs it prints can be pasted into circuit.html and race.html
"""
import requests, json

CIRCUITS = {
    'albert_park': 'Albert_Park_Grand_Prix_Circuit',
    'bahrain': 'Bahrain_International_Circuit',
    'jeddah': 'Jeddah_Street_Circuit', 
    'shanghai': 'Shanghai_International_Circuit',
    'miami': 'Miami_International_Autodrome',
    'imola': 'Autodromo_Enzo_e_Dino_Ferrari',
    'monaco': 'Circuit_de_Monaco',
    'villeneuve': 'Circuit_Gilles_Villeneuve',
    'catalunya': 'Circuit_de_Barcelona-Catalunya',
    'red_bull_ring': 'Red_Bull_Ring',
    'silverstone': 'Silverstone_Circuit',
    'hungaroring': 'Hungaroring',
    'spa': 'Circuit_de_Spa-Francorchamps',
    'zandvoort': 'Circuit_Zandvoort',
    'monza': 'Autodromo_Nazionale_Monza',
    'baku': 'Baku_City_Circuit',
    'marina_bay': 'Marina_Bay_Street_Circuit',
    'suzuka': 'Suzuka_International_Racing_Course',
    'losail': 'Losail_International_Circuit',
    'americas': 'Circuit_of_the_Americas',
    'rodriguez': 'Autodromo_Hermanos_Rodriguez',
    'interlagos': 'Autodromo_Jose_Carlos_Pace',
    'vegas': 'Las_Vegas_Street_Circuit',
    'yas_marina': 'Yas_Marina_Circuit',
}

photos = {}
for circuit_id, article in CIRCUITS.items():
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{article}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            thumb = data.get('thumbnail', {}).get('source', '')
            # Get larger version (replace width)
            if thumb:
                thumb = thumb.replace('/320px-', '/800px-').replace('/160px-', '/800px-')
            photos[circuit_id] = thumb or ''
            print(f"✅ {circuit_id}: {thumb[:80]}")
        else:
            photos[circuit_id] = ''
            print(f"❌ {circuit_id}: HTTP {r.status_code}")
    except Exception as e:
        photos[circuit_id] = ''
        print(f"❌ {circuit_id}: {e}")

print("\n\nconst CIRCUIT_PHOTOS = {")
for k, v in photos.items():
    print(f"  '{k}': '{v}',")
print("};")

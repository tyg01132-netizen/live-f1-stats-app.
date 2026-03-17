# 🏎 F1FORLIVE

> Live Formule 1 dashboard — standen, kalender, race-uitslagen, live timing en meer.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat-square&logo=flask)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

---

## 📸 Wat is het?

F1FORLIVE is een volledig zelfgebouwd F1 dashboard gemaakt met Python (Flask) en vanilla JavaScript. Alle data komt live van de officiële F1 APIs — geen database, geen login, gewoon opstarten en kijken.

**Pagina's:**

| Pagina | Inhoud |
|--------|--------|
| `/` | Homepage — volgende race, countdown, standen |
| `/calendar` | Volledige seizoenskalender + ICS export |
| `/race/2026/1` | Race uitslag, kwalificatie, pitstops, sectortijden |
| `/stats` | Seizoensstatistieken — winnaars, poles, snelste rondes |
| `/live` | Live timing tijdens sessies via OpenF1 |
| `/map` | Wereldkaart met alle circuits |
| `/compare` | Coureur- en seizoenvergelijker |
| `/predictor` | Kampioenschapsprognose |
| `/timeline` | F1 geschiedenis 1950–2026 + kalender export |
| `/info` | Circuits, coureurs, teams, uitzendgids |
| `/history` | Archief — elk seizoen terug tot 1950 |
| `/f2` | Formule 2 data |

---

## ⚙️ Installatie (lokaal)

**Vereisten:** Python 3.9+

```bash
# 1. Clone de repo
git clone https://github.com/tyg01132-netizen/f1-dashboard.git
cd f1-dashboard

# 2. Installeer packages
pip install -r requirements.txt

# 3. Start de app
python app.py
```

Open daarna **http://localhost:5000** in je browser.

---

## 🚀 Deployment (Render)

De repo bevat een `render.yaml` — Render pikt dit automatisch op.

1. Push naar GitHub
2. Render → New Web Service → koppel deze repo
3. Render deployt automatisch via:
   ```
   gunicorn app:app --workers 2 --timeout 60
   ```

Live URL: **https://f1forlive.onrender.com**

---

## 🔌 Data bronnen

| Bron | Wat |
|------|-----|
| [Jolpica/Ergast API](https://api.jolpi.ca) | Standen, resultaten, kalender, kwalificatie |
| [OpenF1 API](https://openf1.org) | Live timing, sectortijden, snelheidstrap, pitstops |
| [wttr.in](https://wttr.in) | Weerdata per circuit |
| [Wikipedia REST API](https://en.wikipedia.org/api) | Circuit foto's |

Alle APIs zijn gratis en vereisen geen API key.

---

## ⚠️ 2026 Seizoen — Afgelaste races

De **Bahrein Grand Prix** (12 april) en **Saoedi-Arabische Grand Prix** (19 april) zijn officieel afgelast vanwege het conflict in het Midden-Oosten. Het seizoen 2026 telt daardoor **22 races** in plaats van 24.

---

## 📁 Structuur

```
f1-dashboard/
├── app.py              ← Flask backend + alle API routes
├── requirements.txt
├── render.yaml         ← Render deployment config
├── templates/          ← HTML pagina's (Jinja2)
│   ├── index.html
│   ├── race.html
│   ├── calendar.html
│   └── ...
└── static/
    ├── app.js          ← Gedeelde JS (helpers, flags, fetch)
    ├── style.css       ← Alle styling
    └── favicon.svg
```

---

## 🛠 Tech stack

- **Backend:** Python 3 · Flask · Gunicorn
- **Frontend:** Vanilla HTML/CSS/JS · Barlow Condensed font · Leaflet.js (kaarten)
- **Hosting:** Render (free tier)
- **Cache:** In-memory server-side cache (5–30 min TTL per endpoint)

---

## 📄 Licentie

MIT — doe er mee wat je wil.

---

*Gebouwd door [@tyg01132-netizen](https://github.com/tyg01132-netizen)*

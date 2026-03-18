# 🏎 F1FORLIVE

> Live Formule 1 dashboard — standen, kalender, race-uitslagen, live timing, weer en meer.

[![Live](https://img.shields.io/badge/🌐_Live-f1forlive.onrender.com-e10600?style=flat-square)](https://f1forlive.onrender.com)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat-square&logo=flask)

---

## 🌐 Live

**[f1forlive.onrender.com](https://f1forlive.onrender.com)**

---

## 📸 Wat is het?

F1FORLIVE is een volledig zelfgebouwd F1 dashboard met Python (Flask) en vanilla JavaScript. Alle data komt live van gratis F1 APIs — geen database, geen login, gewoon opstarten en kijken. Volledig responsive voor mobiel en desktop, met dark/light mode.

---

## 📄 Pagina's

| URL | Inhoud |
|-----|--------|
| `/` | Homepage — volgende race, circuit foto, countdown, weer + strategie, standen |
| `/calendar` | Volledige seizoenskalender + ICS export |
| `/race/2026/3` | Race uitslag, kwalificatie, pitstops, sectortijden, speed trap, replay |
| `/stats` | Seizoensstatistieken — winnaars, poles, snelste rondes |
| `/live` | Live timing + YouTube stream |
| `/map` | Wereldkaart met alle circuits (Leaflet.js) |
| `/compare` | Coureur- en seizoenvergelijker |
| `/predictor` | Kampioenschapsprognose |
| `/simulator` | "What-if" simulator — vul zelf raceuitslagen in |
| `/timeline` | F1 geschiedenis 1950–2026 + kalender export + countdown widget |
| `/info` | Circuits, coureurs, teams, reglementen, uitzendgids |
| `/history` | Archief — elk seizoen terug tot 1950 |
| `/f2` | Formule 2 data |
| `/widget/countdown` | Embeddable countdown widget (iframe) |

---

## ⚠️ 2026 — Afgelaste races

De **Bahrein GP** (12 apr) en **Saoedi-Arabische GP** (19 apr) zijn officieel afgelast vanwege het conflict in het Midden-Oosten. Het seizoen 2026 telt **22 races**.

---

## ⚙️ Lokaal draaien

```bash
git clone https://github.com/tyg01132-netizen/live-f1-stats-app.
cd live-f1-stats-app.
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**

---

## 🚀 Deployment

Gehost op **[Render.com](https://render.com)** via `render.yaml`:

```
gunicorn app:app --workers 2 --timeout 60
```

Elke push naar `main` deployt automatisch.

---

## 🔌 Data bronnen

| Bron | Wat |
|------|-----|
| [Jolpica/Ergast](https://api.jolpi.ca) | Standen, resultaten, kalender, kwalificatie |
| [OpenF1](https://openf1.org) | Live timing, sectortijden, pitstops, snelheidstrap |
| [wttr.in](https://wttr.in) | Weervoorspelling per circuit + strategie-advies |
| [Wikipedia REST API](https://en.wikipedia.org/api) | Circuit fotos |

Alle APIs zijn **gratis** en vereisen **geen API key**.

---

## ✨ Features

- 🌙 Dark / Light mode (volgt systeeminstellingen)
- 📱 Volledig mobiel responsive
- ⚡ Server-side cache (5-30 min TTL)
- 🌤 Weervoorspelling + bandenstrategie per race
- 🏆 Kampioenschap "what-if" simulator
- 📅 ICS kalender export
- 🔗 Embeddable countdown widget
- 🔔 Push notificaties voor sessieherinneringen
- 🗺 Interactieve wereldkaart (Leaflet.js)
- 📺 Live F1 YouTube stream embed

---

## 🛠 Tech stack

**Backend:** Python 3 · Flask · Gunicorn
**Frontend:** Vanilla HTML/CSS/JS · Barlow Condensed · Leaflet.js
**Hosting:** Render (free tier)

---

*Made with ❤️ by admin@ssel*

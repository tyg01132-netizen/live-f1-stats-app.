# 🏎️ F1 Dashboard — Installatiegids

## Wat heb je nodig?
- **Python 3.9 of hoger** (check met `python --version` in de terminal)
- Internetverbinding (voor F1 data)

---

## Stap 1 — Python installeren (als je dat nog niet hebt)
Download Python via: https://www.python.org/downloads/
✅ Vink tijdens installatie aan: **"Add Python to PATH"**

---

## Stap 2 — De map openen in de terminal

### Windows:
1. Open de map `f1-dashboard` in Verkenner
2. Klik in de adresbalk, type `cmd`, druk Enter
3. Je bent nu in de goede map

### Mac:
1. Open Terminal
2. Type: `cd ~/Downloads/f1-dashboard` (pas pad aan)

---

## Stap 3 — Packages installeren

Voer dit commando uit in de terminal:
```
pip install -r requirements.txt
```

⏳ Dit kan 1-2 minuten duren (FastF1 is een grote library).

---

## Stap 4 — De app starten

```
python app.py
```

Je ziet zoiets als:
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

---

## Stap 5 — App openen in browser

Ga naar: **http://localhost:5000**

🎉 De F1 Dashboard is nu live!

---

## Pagina's

| URL | Inhoud |
|-----|--------|
| `localhost:5000` | Home — laatste race, volgende race, standen |
| `localhost:5000/calendar` | Volledige seizoenskalender 2024 |
| `localhost:5000/drivers` | Alle coureurs met punten grafiek |
| `localhost:5000/driver/max_verstappen` | Coureur detail pagina |
| `localhost:5000/race/1` | Race uitslag ronde 1 |
| `localhost:5000/live` | Live sessie data (via OpenF1) |

---

## Problemen?

**"pip is not recognized"** → Probeer `python -m pip install -r requirements.txt`

**Foutmelding bij FastF1** → Probeer: `pip install fastf1 --upgrade`

**Pagina laadt niet** → Controleer of `python app.py` nog actief is in de terminal

**Data laadt niet** → Controleer je internetverbinding; externe API's zijn nodig

---

## App stoppen
Druk `CTRL + C` in de terminal.

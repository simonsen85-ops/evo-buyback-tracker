# Evolution AB — Buyback Tracker

Bloomberg-inspireret tracker for Evolution AB's (EVO.ST) aktietilbagekøbsprogram.

## Funktioner

- **Realtidskurs** fra Yahoo Finance (auto-opdatering ons + fre)
- **Komplet buyback-historik** med alle offentliggjorte trancher
- **Værdiskabelsesmodel**: FCF yield, EPS-accretion, net buyback (buyback − SBC)
- **2026 kapitalallokering**: Status og scenarieanalyse

## Filer

| Fil | Formål |
|-----|--------|
| `index.html` | Tracker-dashboardet |
| `data.json` | Struktureret buyback-data |
| `scraper.py` | Auto-opdatering af kursdata |
| `.github/workflows/update.yml` | GitHub Actions schedule |

## Auto-opdatering

GitHub Actions kører `scraper.py` onsdag og fredag kl. 18:00 CET.
Scriptet henter seneste EVO.ST-kurs fra Yahoo Finance og opdaterer `index.html`.

Buyback-trancher opdateres manuelt i `data.json` når Evolution offentliggør nye Cision-pressemeddelser.

## Manuel opdatering af buyback-data

Når Evolution offentliggør en ny tranche på [evolution.com/investors/press-releases](https://www.evolution.com/investors/press-releases/):

1. Åbn `data.json` i GitHub (klik filen → ✏️)
2. Tilføj ny tranche i `tranches`-arrayet
3. Commit ændringen

## Design

Samme designsystem som [FED Buyback Tracker](https://simonsen85-ops.github.io/fed-buyback-tracker/):
- JetBrains Mono + Outfit fonts
- 4-niveau typehierarki (T1–T4)
- Grønt spektrum for værdimetrikker (G1–G4)
- Bloomberg-inspireret mørkt layout

---

*Ikke investeringsrådgivning.*

# Evolution AB — Buyback Tracker (modular upgrade)

This upgrades the existing `evo-buyback-tracker` repo to use automated
scraping via a Cision news source module.

## What's new

**Before:** `scraper.py` only updated the price from Yahoo Finance. Buyback
transaction data had to be manually added to `data.json` from Cision PDFs.

**After:** The new modular scraper automatically fetches buyback announcements
from `news.cision.com/evolution`, parses the weekly transaction tables, and
updates `data.json`. Same modular architecture as the FED tracker.

## File structure

```
evo-buyback-tracker/
├── .github/workflows/update.yml      ← REPLACE existing
├── data.json                         ← pre-populated with €500M program data
├── index.html                        ← keep existing dashboard (unchanged)
└── scripts/
    ├── scraper.py                    ← NEW thin orchestrator
    └── sources/                      ← NEW modular sources
        ├── __init__.py
        ├── base.py                   ← Announcement dataclass
        ├── cision.py                 ← NEW: news.cision.com parser
        └── volume/
            ├── __init__.py
            ├── nasdaq.py             ← Nasdaq volume API
            ├── yahoo.py              ← Yahoo Finance fallback
            └── compute.py            ← 25% Safe Harbour calculations
```

## Deploy instructions

### Option A: GitHub web UI (no terminal)

1. Go to `simonsen85-ops/evo-buyback-tracker` on github.com
2. Click **Add file → Upload files**
3. Drag the entire `scripts/` folder from the extracted tarball into the upload area
4. Drag `update.yml` and move it to `.github/workflows/update.yml`
5. Commit: "Modular refactor: add automated Cision scraping"

### Option B: GitHub Codespaces (easier for folder moves)

1. Open Codespace on the repo
2. In terminal:
   ```bash
   tar -xzf ~/Downloads/evo-modular-refactor.tar.gz
   # Files land in correct structure automatically
   rm ~/Downloads/evo-modular-refactor.tar.gz
   git add -A
   git commit -m "Modular refactor: automated Cision scraping"
   git push
   ```

### Option C: Local git

```bash
cd path/to/evo-buyback-tracker
tar -xzf ~/Downloads/evo-modular-refactor.tar.gz
git add -A
git commit -m "Modular refactor: automated Cision scraping"
git push
```

## Verify deployment

1. Go to **Actions** tab → "Scrape & Deploy Evolution Buyback Tracker"
2. Click **Run workflow** → **Run workflow** (manual trigger)
3. Wait ~30 seconds for completion

### Expected log output

```
Evolution AB — Buyback Scraper (modular)
Existing announcements: N

[cision] Scanning for evolution...
  [cision] Found ~40 buyback releases in listings
  [cision] ✓ 2025-12-08: week 133140sh / acc 4481648sh
  [cision] ✓ 2025-12-01: week 142000sh / acc 4348508sh
  [cision] ✓ 2025-11-21: week 432000sh / acc 1267038sh
  ...
  [cision] merged N new announcement(s)

Fetching trading volumes...
  [nasdaq] chart/download: ~250 daily volumes
  [yahoo] EVO.ST: ~500 daily entries
  Merged: ~500 days

Fetching current price...
  Current price: XXX SEK

Saved N announcements to data.json
```

## Known limitations

- **HTML scraping may fail** if Cision changes its listing/release HTML
  structure. Fallback strategies are built in (URL slug → title). If
  scraping breaks entirely, we can add PDF parsing as fallback (PDFs at
  `mb.cision.com/Main/12069/...` are more stable).

- **Sandbox 403**: Both Cision and Yahoo Finance returned 403 when tested
  from Claude's sandbox environment. GitHub Actions runners have different
  IP ranges and normally don't trigger this. Past FED tracker runs worked
  the same way despite sandbox 403.

- **No dashboard changes**: This upgrade is scraper-only. Your existing
  `index.html` dashboard continues to work as-is, reading the same
  `data.json` format. Additional fields are added (`uid`, `source`,
  `daily_volume_detail`) but these are ignored by the existing dashboard.

## Config in scripts/scraper.py

To adapt this pattern for another Swedish/Nordic stock that uses Cision:

```python
COMPANY_NAME = "Evolution AB"
CISION_SLUG = "evolution"               # news.cision.com/<slug>
UID_PREFIX = "evo"
YAHOO_TICKER = "EVO.ST"
NASDAQ_INSTRUMENT_ID = "TX1757078"     # find at api.nasdaq.com
TOTAL_SHARES = 204462162                # update when shares cancelled
```

## Next buyback program

AGM is 24 April 2026. If a new program is decided, add it to the `PROGRAMS`
list in `scripts/scraper.py`:

```python
PROGRAMS = [
    { "id": 1, "name": "€500M (FY2025)", ... },  # existing, completed
    {
        "id": 2,
        "name": "€XXXm (FY2026)",
        "start": "2026-04-25",
        "end": "2027-04-xx",
        "max_amount_eur": XXX,
        "announced": "2026-04-24",
        "closed_on": None,
    },
]
```

# Evolution AB — Buyback Tracker (modular upgrade)

Automated Nordic buyback tracker using **Nasdaq Nordic's public news API**
as the primary regulatory source.

## What's new

**Before:** `scraper.py` only fetched the price from Yahoo Finance. All
buyback transaction data had to be manually copied from Cision PDFs
into `data.json`.

**After:** Fully automated. The new scraper queries Nasdaq Nordic's
regulatory OAM filing system — the same system where Evolution is *legally
required* to file its buyback transactions under MAR (Market Abuse
Regulation). Every week's new release is picked up automatically.

## Why Nasdaq News API instead of Cision?

Key learning from this iteration: **Always prefer primary regulatory
sources over commercial distributors.**

Evolution files the same buyback data to three places simultaneously:
1. **Nasdaq Nordic's OAM** (legally required regulatory filing)
2. **Cision** (commercial PR distribution service)
3. **evolution.com** (company's own site)

Cision would be tempting — the release pages have clean data — but:
- The listing page is JavaScript-rendered (blank HTML to scrapers)
- The public JSON API requires a per-company feed ID from Cision sales
- It's commercial infrastructure we'd be using without an agreement

Nasdaq's OAM system has a **public JSON API** at
`api.news.eu.nasdaq.com/news/query.action` — discovered via browser
DevTools. It's:
- Public and free (no auth required)
- Stable (regulatory infrastructure, not marketing tech)
- Covers all Nordic-listed companies (scales to Hacksaw, etc.)

## File structure

```
evo-buyback-tracker/
├── .github/workflows/update.yml      ← REPLACE existing workflow
├── data.json                         ← preserved, auto-upgraded on first run
├── index.html                        ← unchanged (existing dashboard)
└── scripts/
    ├── scraper.py                    ← NEW modular orchestrator
    └── sources/
        ├── __init__.py
        ├── base.py                   ← Announcement dataclass
        ├── nasdaq_news.py            ← NEW: api.news.eu.nasdaq.com parser
        └── volume/
            ├── __init__.py
            ├── nasdaq.py             ← Nasdaq volume API (already working)
            ├── yahoo.py              ← Yahoo Finance fallback
            └── compute.py            ← 25% Safe Harbour calculations
```

## Deploy instructions

### Via Codespaces (recommended, ~2 minutes)

1. Open `simonsen85-ops/evo-buyback-tracker` on github.com
2. Click **Code** (green) → **Codespaces** → **Create codespace on main**
3. Drag `evo-modular-refactor.tar.gz` into the file tree (left panel)
4. In the terminal:
   ```bash
   tar -xzf evo-modular-refactor.tar.gz --strip-components=1
   rm evo-modular-refactor.tar.gz
   git add -A
   git commit -m "Switch to Nasdaq News API (primary regulatory source)"
   git push
   ```
5. Close the Codespace

### Via GitHub web UI (if you prefer no terminal)

If you already deployed the previous version via Codespace earlier today,
you only need to change two things:

1. **Delete** `scripts/sources/cision.py` (legacy from previous attempt)
2. **Upload** `scripts/sources/nasdaq_news.py` to the same folder
3. **Replace** `scripts/scraper.py` with the new version

All other files (base.py, volume/*, update.yml) are unchanged.

## Verify the deployment

1. Go to **Actions** → "Scrape & Deploy Evolution Buyback Tracker"
2. Click **Run workflow** → **Run workflow** (green button)
3. Wait ~30 seconds for completion

### Expected log output (first run)

```
Evolution AB — Buyback Scraper (modular)
Existing announcements: 0

[nasdaq_news] Scanning for Evolution AB...
  [nasdaq_news] Found ~45 English buyback releases in listings
  [nasdaq_news] ✓ 2025-12-15: week 133140sh @ 622.66 / acc 1618178sh
  [nasdaq_news] ✓ 2025-12-08: week ... / acc ...
  [nasdaq_news] ✓ 2025-12-01: week ... / acc ...
  ... (many more)
  [nasdaq_news] merged ~45 new announcement(s)

Fetching trading volumes...
  [nasdaq] chart/download: ~250 daily volumes
  [yahoo] EVO.ST: ~500 daily entries

Fetching current price...
  Current price: XXX SEK
```

## API details (for debugging/maintenance)

### Listing endpoint

```
GET https://api.news.eu.nasdaq.com/news/query.action
  ?globalGroup=exchangeNotice
  &globalName=NordicAllMarkets
  &displayLanguage=en
  &cnsCategory=Changes in company's own shares
  &company=Evolution AB
  &dir=DESC&limit=10&start=0
  &callback=handleResponse
```

Returns JSONP wrapped JSON:
```javascript
handleResponse({
  "results": {
    "item": [
      {
        "disclosureId": 1406187,
        "headline": "Acquisitions of own shares in Evolution AB (publ)",
        "language": "en",
        "messageUrl": "https://view.news.eu.nasdaq.com/view?id=...",
        "releaseTime": "2025-12-15 08:30:00",
        "company": "Evolution AB",
        "cnsCategory": "Changes in company's own shares"
      }, ...
    ]
  },
  "count": 90
});
```

### Per-release detail

Each `messageUrl` returns full HTML with transaction tables.

## Config in scripts/scraper.py

To adapt this for another Nordic-listed company (Hacksaw, EQT, Essity, etc.):

```python
COMPANY_NAME = "Evolution AB"          # Exact name as filed with Nasdaq
UID_PREFIX = "evo"
YAHOO_TICKER = "EVO.ST"                # Stockholm ticker
NASDAQ_INSTRUMENT_ID = "TX1757078"     # from api.nasdaq.com
TOTAL_SHARES = 204462162                # update when shares cancelled
```

The `nasdaq_news.py` source is company-agnostic — same code works for
any Nordic-listed company by just changing `company_name`.

## Next buyback program

AGM is 24 April 2026. If a new buyback program is announced:

```python
PROGRAMS = [
    { "id": 1, "name": "€500M (FY2025)", ... },  # existing, completed
    {
        "id": 2,
        "name": "€XXXm (FY2026)",
        "start": "2026-04-25",
        "end": "2027-04-xx",
        "max_amount_eur": XXX_000_000,
        "announced": "2026-04-24",
        "closed_on": None,
    },
]
```

Also update `TOTAL_SHARES` if shares are cancelled post-program.

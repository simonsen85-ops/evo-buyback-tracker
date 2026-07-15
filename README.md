# Evolution AB — Buyback Tracker

Live tracker for Evolution AB's (EVO.ST) share buyback program.
Same modular architecture as the FED and IMB trackers.

**Live dashboard:** https://simonsen85-ops.github.io/evo-buyback-tracker/

## Architecture

```
evo-buyback-tracker/
├── .github/workflows/scrape.yml     # Daily auto-update (weekdays 17:30 CET)
├── scripts/
│   ├── scraper.py                   # Thin orchestrator
│   ├── build_html.py                # Generates index.html from data.json
│   └── sources/
│       ├── __init__.py
│       ├── base.py                  # Announcement dataclass + ABC + merge
│       ├── parsing.py               # Shared HTML/text parsers
│       ├── evolution_html.py        # PRIMARY: evolution.com press release HTML
│       └── volume/
│           ├── compute.py           # Safe Harbour 25% rule calcs
│           ├── nasdaq.py            # Nasdaq Nordic volume API
│           └── yahoo.py             # Yahoo Finance volume fallback
├── data.json                        # All buyback data
├── index.html                       # Generated dashboard (do not edit)
├── requirements.txt
└── README.md
```

## Source choice (first-principles, verified)

**History:** Evolution used Cision as MAR disclosure agent until July 2026,
then migrated to MFN. This changed both the listing URL and PDF hosting:

| Era | Listing | PDFs |
|---|---|---|
| Until Jul 2026 | `/investors/press-releases/` | `mb.cision.com/Main/12069/{id}/{att}.pdf` |
| From Jul 2026 | `/investors/financial-publications/press-releases/` | `storage.mfn.se/{uuid}/{slug}.pdf` |

**Current approach:** The scraper parses Evolution's own server-rendered
press release pages directly (no PDF download needed). Detail pages contain
the full text and a structured HTML table with daily transactions.

Old announcements in data.json keep their `evo-cision-c{id}` UIDs;
new ones use `evo-mfn-{slug}`.

## Active programmes

- **€2 mia. (2026)** — announced 18 May 2026, started 19 May 2026
- 10% cap: 19,922,661 shares
- Backup: €300M RCF (JPMorgan + Citibank)

## Manual run

```bash
python scripts/scraper.py
python scripts/build_html.py
```

To update programmes when announced: edit `PROGRAMS` in `scripts/scraper.py`.

## Not investment advice.

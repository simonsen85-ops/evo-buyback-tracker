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
│       ├── parsing.py               # Shared HTML/text/PDF parsers
│       ├── cision_pdf.py            # PRIMARY: downloads PDFs from mb.cision.com
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

For Evolution AB specifically:

1. **PDFs at mb.cision.com** are the official MAR Article 5 regulatory
   disclosure documents (Evolution's Cision customer ID = `12069`).
2. **evolution.com/investors/press-releases** lists ALL buyback PDFs
   with direct links to mb.cision.com.

The scraper discovers PDF URLs from evolution.com, downloads each PDF,
and extracts text with `pypdf` for parsing.

**Why not the Cision newsroom HTML?** It works, but has Cloudflare bot
detection that occasionally blocks automated fetches. The PDFs are the
canonical regulatory document anyway.

**Why not the Nasdaq News API?** Verified empirically — it only carries
issuer reports + market notices, not weekly Article 5 buybacks.

**Why not Finansinspektionen's OAM?** Sweden's OAM is primarily for MAR
Article 17 inside information and major shareholding notifications, not
weekly Article 5 buybacks. It's also an ASP.NET form with no API.

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

#!/usr/bin/env python3
"""
Evolution AB — Buyback Scraper (orchestrator).

Thin coordinator following the same pattern as FED and IMB trackers:

  sources.cision_pdf.CisionPDFSource    — PRIMARY: downloads PDFs from
                                          mb.cision.com (the official MAR
                                          Article 5 disclosure documents)
                                          via URLs discovered on
                                          evolution.com/investors
  sources.volume.compute                — Safe Harbour calculations
  sources.volume.nasdaq / yahoo         — volume data providers

Flow:
  1. Load data.json
  2. Discover buyback PDF URLs from evolution.com IR listing
  3. Download each PDF, extract text with pypdf, parse
  4. Dedup & merge into data.json (UID = evo-cision-c{cision_id})
  5. Fetch daily volume data (Nasdaq Nordic primary, Yahoo fallback)
  6. Compute Safe Harbour metrics (25% rule)
  7. Fetch current price (Yahoo)
  8. Save data.json

Run:
  python scripts/scraper.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sources.base import merge_announcements
from sources.cision_pdf import CisionPDFSource
from sources.volume.compute import (
    build_daily_volume_dict,
    compute_safe_harbour_metrics,
)
from sources.volume.yahoo import fetch_yahoo_current_price


# ============================================================
# CONFIG — Evolution-specific
# ============================================================
DATA_FILE = Path(__file__).parent.parent / "data.json"

# Company identity
COMPANY_NAME = "Evolution AB (publ)"
UID_PREFIX = "evo"
YAHOO_TICKER = "EVO.ST"

# Nasdaq Nordic instrument ID for EVO.ST — used by the volume API.
# Find/verify via Chrome DevTools on https://www.nasdaq.com/european-market-activity/shares/evo
NASDAQ_INSTRUMENT_ID = "TX1757078"
NASDAQ_REFERER = (
    "https://www.nasdaq.com/european-market-activity/shares/evo?id=SSE107867"
)

# Share count (post-cancellation, from new programme announcement 18 May 2026)
TOTAL_SHARES = 199226613

# Buyback programs — UPDATE when new programs are announced
PROGRAMS = [
    {
        "id": 1,
        "name": "€400M (2023 AGM)",
        "start": "2023-11-23",
        "end": "2024-07-17",
        "max_eur": 400000000,
        "announced": "2023-11-23",
        "closed_on": "2024-07-17",
    },
    {
        "id": 2,
        "name": "€400M (2024 AGM I)",
        "start": "2024-07-18",
        "end": "2024-10-31",
        "max_eur": 400000000,
        "announced": "2024-07-18",
        "closed_on": "2024-10-31",
    },
    {
        "id": 3,
        "name": "€500M (2025)",
        "start": "2025-02-10",
        "end": "2025-12-08",
        "max_eur": 500000000,
        "announced": "2025-02-10",
        "closed_on": "2025-12-08",
    },
    {
        "id": 4,
        "name": "€2 mia. (2026)",
        "start": "2026-05-19",
        "end": "2027-04-30",  # Anticipated by next AGM; updates when closed
        "max_eur": 2000000000,
        "announced": "2026-05-18",
        "closed_on": None,
    },
]


# ============================================================
# Data load/save
# ============================================================
def load_data() -> dict:
    """Load data.json, or return a fresh empty structure."""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "company": COMPANY_NAME,
        "ticker": YAHOO_TICKER,
        "exchange": "Nasdaq Stockholm",
        "total_shares": TOTAL_SHARES,
        "currency": "SEK",
        "programs": PROGRAMS,
        "announcements": [],
        "last_updated": None,
    }


def save_data(data: dict) -> None:
    """Persist data.json."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(data['announcements'])} announcements to {DATA_FILE}")


# ============================================================
# Announcement fetching
# ============================================================
def fetch_all_announcements(data: dict) -> int:
    """
    Fetch from configured sources in priority order, merge into data['announcements'].
    Returns number of new announcements added.
    """
    sources = [
        CisionPDFSource(
            uid_prefix=UID_PREFIX,
            programs=PROGRAMS,
        ),
    ]

    total_new = 0
    for src in sources:
        try:
            announcements = src.fetch_recent(max_announcements=30)
        except Exception as e:
            print(f"  [{src.name}] failed: {e}")
            continue

        updated_list, added = merge_announcements(
            data["announcements"], announcements
        )
        data["announcements"] = updated_list
        total_new += added
        print(f"  [{src.name}] merged {added} new announcement(s)")

    return total_new


# ============================================================
# Cross-program rollup of acc_amount
# ============================================================
def recompute_program_accumulators(data: dict) -> None:
    """
    Recompute acc_amount per program by summing weekly amounts in chronological order.
    (The source PR sometimes omits acc_amount, so we compute it from week_amount.)
    """
    by_program: dict[int, int] = {}
    sorted_anns = sorted(data["announcements"], key=lambda a: a.get("period_start", ""))
    for a in sorted_anns:
        pid = a.get("program_id")
        if pid is None:
            continue
        running = by_program.get(pid, 0) + (a.get("week_amount") or 0)
        a["acc_amount"] = running
        by_program[pid] = running


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print(f"{COMPANY_NAME} — Buyback Scraper (modular)")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    data = load_data()
    print(f"Existing announcements: {len(data['announcements'])}")

    # Always refresh config (in case manually edited)
    data["company"] = COMPANY_NAME
    data["ticker"] = YAHOO_TICKER
    data["exchange"] = "Nasdaq Stockholm"
    data["currency"] = "SEK"
    data["total_shares"] = TOTAL_SHARES
    data["programs"] = PROGRAMS

    # 1. Fetch announcements
    print("\nFetching announcements...")
    new_count = fetch_all_announcements(data)
    data["announcements"].sort(key=lambda a: a.get("announcement_date", ""))

    # 2. Recompute program-level accumulators
    recompute_program_accumulators(data)

    # 3. Volume + Safe Harbour
    daily_vol, source_map = build_daily_volume_dict(
        data,
        instrument_id=NASDAQ_INSTRUMENT_ID,
        referer_url=NASDAQ_REFERER,
        yahoo_ticker=YAHOO_TICKER,
    )
    compute_safe_harbour_metrics(data["announcements"], daily_vol, source_map)

    # 4. Current price
    print("\nFetching current price...")
    price = fetch_yahoo_current_price(YAHOO_TICKER)
    if price:
        data["current_price"] = price
        print(f"  Current price: {price} SEK")

    # 5. Save
    save_data(data)

    print(f"\nDone. {new_count} new announcement(s) added.")
    print(f"Total: {len(data['announcements'])} announcements")

    if data["announcements"]:
        last = data["announcements"][-1]
        print(
            f"Latest: {last.get('announcement_date')} — "
            f"{last.get('week_shares', 0):,} shares, "
            f"SEK {last.get('week_amount', 0):,} "
            f"(source: {last.get('source', '?')})"
        )


if __name__ == "__main__":
    main()

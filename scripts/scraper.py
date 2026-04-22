#!/usr/bin/env python3
"""
Evolution AB — Buyback Scraper (orchestrator).

Thin coordinator. Real work lives in sources/:
  sources.nasdaq_news.NasdaqNewsSource  — primary announcement source
  sources.volume.compute                — Safe Harbour calculations
  sources.volume.nasdaq / yahoo         — volume data providers

Data source: Nasdaq Nordic News API (primary regulatory source).
  api.news.eu.nasdaq.com/news/query.action — OAM filings for Nordic companies.

Flow:
  1. Load data.json
  2. Fetch recent announcements from Nasdaq News API
  3. Dedup & merge into data.json
  4. Fetch daily volume data (Nasdaq primary, Yahoo fallback)
  5. Compute Safe Harbour metrics (25% rule)
  6. Fetch current price (Yahoo)
  7. Save data.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sources.base import merge_announcements
from sources.nasdaq_news import NasdaqNewsSource
from sources.volume.compute import (
    build_daily_volume_dict,
    compute_safe_harbour_metrics,
)
from sources.volume.yahoo import fetch_yahoo_current_price


# ============================================================
# CONFIG — change these when adapting to another stock
# ============================================================
DATA_FILE = Path(__file__).parent.parent / "data.json"

# Company identity
COMPANY_NAME = "Evolution AB"          # Exact name as filed with Nasdaq Nordic
UID_PREFIX = "evo"
YAHOO_TICKER = "EVO.ST"                # Stockholm Stock Exchange
NASDAQ_INSTRUMENT_ID = "TX1757078"     # from api.nasdaq.com for EVO
NASDAQ_REFERER = (
    "https://www.nasdaq.com/european-market-activity/shares/evo?id=TX1757078"
)

# Share count baseline (for NAV/dilution calculations)
# This changes when shares are cancelled — keep current value here
TOTAL_SHARES = 204462162   # as of November 2025; will need manual update

# NAV is not applicable to Evolution (not a REIT) — we use share count
# and EPS for value calculations. Keep an empty list for UI compatibility.
NAV_HISTORY = []

# Buyback programs — UPDATE when new programs are announced.
# Evolution's programs are measured in EUR amounts, converted to shares at
# execution time. We track them as sequential programs with start/end dates.
PROGRAMS = [
    {
        "id": 1,
        "name": "€500M (FY2025)",
        "start": "2025-02-11",
        "end": "2025-12-08",
        "max_amount_eur": 500_000_000,
        "max_shares": 20_446_216,        # 10% of share capital cap
        "announced": "2025-02-10",
        "closed_on": "2025-12-08",        # Program completed
        "currency": "EUR",
    },
    # Next program to be announced at AGM 24 April 2026 — will be added here
]


# ============================================================
# Legacy migration
# ============================================================
def _ensure_uids(data: dict) -> int:
    """
    Ensure every existing announcement has a 'uid' field.
    Old entries (added manually from Cision PDFs before the modular refactor)
    don't have uids. Generate stable ones from period_end + acc_shares.
    """
    migrated = 0
    for a in data.get("announcements", []):
        if not a.get("uid"):
            date = a.get("announcement_date") or a.get("period_end", "unknown")
            acc = a.get("acc_shares", 0)
            a["uid"] = f"{UID_PREFIX}-legacy-{date}-{acc}"
            a.setdefault("source", "legacy")
            migrated += 1
    if migrated:
        print(f"Migrated {migrated} legacy announcements (added uid/source fields)")
    return migrated


def _dedup_by_period(data: dict) -> int:
    """
    Remove duplicates where same period_start+period_end+acc_shares appear
    from multiple sources. Prefer nasdaq_news > cision > legacy.
    """
    announcements = data.get("announcements", [])
    by_period: dict[tuple, list[int]] = {}
    for i, a in enumerate(announcements):
        key = (a.get("period_start"), a.get("period_end"), a.get("acc_shares"))
        by_period.setdefault(key, []).append(i)

    to_remove = set()
    priority = {"nasdaq_news": 0, "cision": 1, "legacy": 2}
    for key, indices in by_period.items():
        if len(indices) <= 1 or key == (None, None, None):
            continue
        indices_sorted = sorted(
            indices,
            key=lambda i: priority.get(announcements[i].get("source", "legacy"), 99),
        )
        for i in indices_sorted[1:]:
            to_remove.add(i)

    if to_remove:
        data["announcements"] = [
            a for i, a in enumerate(announcements) if i not in to_remove
        ]
        print(f"Removed {len(to_remove)} duplicate announcement(s)")
    return len(to_remove)


# ============================================================
# Data load/save
# ============================================================
def load_data() -> dict:
    """Load data.json, or return a fresh empty structure.

    Robust to legacy data.json files that may have a different schema —
    ensures all required fields exist (adding defaults if missing) so
    downstream code doesn't fail with KeyError.
    """
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Ensure all required fields exist, filling in defaults if missing.
    # This makes the scraper compatible with any previous data.json format.
    defaults = {
        "company_name": COMPANY_NAME,
        "total_shares": TOTAL_SHARES,
        "nav_history": NAV_HISTORY,
        "programs": PROGRAMS,
        "currency": "SEK",
        "program_currency": "EUR",
        "announcements": [],
        "last_updated": None,
    }
    for key, default_value in defaults.items():
        if key not in data:
            data[key] = default_value

    return data


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
    Fetch from all configured sources, merge into data['announcements'].
    Returns number of new announcements added.
    """
    sources = [
        NasdaqNewsSource(
            company_name=COMPANY_NAME,
            uid_prefix=UID_PREFIX,
            max_listing_pages=10,  # 10 pages × 10 items = up to 100 releases scanned
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
# Main
# ============================================================
def main():
    print("=" * 60)
    print(f"{COMPANY_NAME} — Buyback Scraper (modular)")
    print(f"Run time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    data = load_data()
    print(f"Existing announcements: {len(data['announcements'])}")

    _ensure_uids(data)

    new_count = fetch_all_announcements(data)

    _dedup_by_period(data)

    data["announcements"].sort(key=lambda a: a.get("announcement_date", ""))

    daily_vol, source_map = build_daily_volume_dict(
        data,
        instrument_id=NASDAQ_INSTRUMENT_ID,
        referer_url=NASDAQ_REFERER,
        yahoo_ticker=YAHOO_TICKER,
    )
    compute_safe_harbour_metrics(data["announcements"], daily_vol, source_map)

    print("\nFetching current price...")
    price = fetch_yahoo_current_price(YAHOO_TICKER)
    if price:
        data["current_price"] = price
        print(f"  Current price: {price} SEK")

    # Refresh config (in case manually edited)
    data["company_name"] = COMPANY_NAME
    data["total_shares"] = TOTAL_SHARES
    data["nav_history"] = NAV_HISTORY
    data["programs"] = PROGRAMS

    save_data(data)

    print(f"\nDone. {new_count} new announcement(s) added.")
    print(f"Total: {len(data['announcements'])} announcements")

    if data["announcements"]:
        last = data["announcements"][-1]
        print(
            f"Latest: {last.get('announcement_date')} — "
            f"{last.get('week_shares')} shares @ {last.get('week_avg_price')} SEK "
            f"(source: {last.get('source', '?')})"
        )


if __name__ == "__main__":
    main()

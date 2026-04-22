"""
Nasdaq Nordic News API source.

PRIMARY REGULATORY SOURCE — preferred over commercial distributors like Cision.

Evolution (and all Nordic-listed companies) must file buyback announcements
with Nasdaq Nordic's Officially Appointed Mechanism (OAM). This data is
exposed through a public JSON API at api.news.eu.nasdaq.com.

API endpoint (discovered via DevTools Network inspection):

  https://api.news.eu.nasdaq.com/news/query.action
    ?globalGroup=exchangeNotice
    &globalName=NordicAllMarkets
    &displayLanguage=en
    &cnsCategory=Changes in company's own shares    ← filter: buybacks only
    &company=Evolution AB                            ← filter: one company
    &dir=DESC                                        ← newest first
    &limit=50 &start=0                               ← pagination

Response format: JSONP (wrapped in `handleResponse({...})` for cross-origin
support in browsers). We strip the wrapper and parse the inner JSON.

Response structure:
  {
    "results": {
      "item": [
        {
          "disclosureId": 1406187,         ← stable unique ID
          "headline": "Acquisitions of own shares in Evolution AB (publ)",
          "language": "en",                ← we filter to English only
          "messageUrl": "https://view.news.eu.nasdaq.com/view?id=...",
          "releaseTime": "2025-12-15 08:30:00",
          "company": "Evolution AB",
          "cnsCategory": "Changes in company's own shares",
          ...
        },
        ...
      ]
    },
    "count": 90                            ← total matching count
  }

For each release we fetch the messageUrl to get the full HTML body, then
parse it to extract the transaction table and accumulated shares.

This approach works for ANY Nordic-listed company that files on Nasdaq:
  - Evolution AB, Hacksaw AB, EQT AB, Essity, Embla Medical, etc.
Simply change the `company` parameter.
"""

import re
import json
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from .base import Announcement, AnnouncementSource


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/javascript, application/json, */*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/european-market-activity/news/company-news",
    "Origin": "https://www.nasdaq.com",
}


# ============================================================
# Helpers — numeric / date parsing
# ============================================================
def _parse_number(s):
    """Parse formatted numbers robustly:
        '9,999,890'    → 9999890 (English thousand separator)
        '210.57'       → 210.57  (English decimal)
        '9.999.890'    → 9999890 (European thousand separator)
        '210,57'       → 210.57  (European decimal)
        '1,234.56'     → 1234.56 (English mixed)
        '1.234,56'     → 1234.56 (European mixed)
    """
    if not s:
        return 0
    s = str(s).strip()
    s = s.replace("\xa0", "").replace(" ", "")

    n_commas = s.count(",")
    n_periods = s.count(".")

    if n_commas > 0 and n_periods > 0:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif n_commas > 1:
        s = s.replace(",", "")
    elif n_periods > 1:
        s = s.replace(".", "")
    elif n_commas == 1:
        parts = s.split(",")
        if len(parts[1]) == 3 and parts[1].isdigit() and parts[0].isdigit():
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def _parse_date_english(s):
    """Parse English dates → 'YYYY-MM-DD' string."""
    if not s:
        return None
    s = s.strip()

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s

    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }

    m = re.match(r"^(\d{1,2})\s+(\w+)\s+(\d{4})$", s)
    if m:
        day, month_name, year = m.groups()
        month = months.get(month_name.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    m = re.match(r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m:
        month_name, day, year = m.groups()
        month = months.get(month_name.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    return None


# ============================================================
# HTML table parser
# ============================================================
class _TableParser(HTMLParser):
    """Extracts all table rows from HTML as list[list[str]]."""
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.in_th = False
        self.current_row = []
        self.rows = []
        self.current_data = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif tag == "td" and self.in_table:
            self.in_td = True
            self.current_data = ""
        elif tag == "th" and self.in_table:
            self.in_th = True
            self.current_data = ""
        elif tag == "tr" and self.in_table:
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "td" and self.in_td:
            self.current_row.append(self.current_data.strip())
            self.in_td = False
        elif tag == "th" and self.in_th:
            self.current_row.append(self.current_data.strip())
            self.in_th = False
        elif tag == "tr" and self.in_table and self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []

    def handle_data(self, data):
        if self.in_td or self.in_th:
            self.current_data += data


# ============================================================
# Release body parser (re-used from Cision approach — same format)
# ============================================================
def _extract_announcement_body(html):
    """
    Parse the transaction table + metadata from a Nasdaq view release HTML.

    Format is consistent across Nordic listed companies:
      Table: Date | Volume | Weighted avg price | Transaction value
      Prose: "Since X up to Y, a total of N shares have been acquired"
             "holding of own shares amounted to N"
             "A maximum of N shares in total may be acquired"
    """
    parser = _TableParser()
    parser.feed(html)
    rows = parser.rows
    if not rows:
        return None

    daily_transactions = []
    for row in rows:
        if len(row) < 3:
            continue
        date_str = _parse_date_english(row[0])
        if not date_str:
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", row[0].strip())
            if m:
                date_str = m.group(1)
        if not date_str:
            continue
        try:
            shares = int(_parse_number(row[1]))
            price = _parse_number(row[2])
            amount = int(_parse_number(row[3])) if len(row) > 3 else int(shares * price)
        except (ValueError, IndexError):
            continue
        if shares > 0 and price > 0:
            daily_transactions.append({
                "date": date_str,
                "shares": shares,
                "price": round(price, 2),
                "amount": amount,
            })

    if not daily_transactions:
        return None

    week_shares = sum(t["shares"] for t in daily_transactions)
    week_amount = sum(t["amount"] for t in daily_transactions)
    week_avg = week_amount / week_shares if week_shares > 0 else 0
    dates_sorted = sorted(t["date"] for t in daily_transactions)
    period_start = dates_sorted[0]
    period_end = dates_sorted[-1]

    prose = re.sub(r"<[^>]+>", " ", html)
    prose = re.sub(r"\s+", " ", prose)

    acc_shares = 0
    m = re.search(
        r"(?:Since|from)\s+\d{1,2}\s+\w+\s+\d{4}\s+"
        r"(?:up to and including\s+\d{1,2}\s+\w+\s+\d{4},?\s+)?"
        r"a total of\s+([\d,\.]+)\s+shares\s+have been acquired",
        prose, re.IGNORECASE,
    )
    if m:
        acc_shares = int(_parse_number(m.group(1)))

    acc_holdings = 0
    m = re.search(
        r"holding of own shares amount(?:ed|s) to\s+([\d,\.]+)",
        prose, re.IGNORECASE,
    )
    if m:
        acc_holdings = int(_parse_number(m.group(1)))

    max_shares = 0
    m = re.search(
        r"A maximum of\s+([\d,\.]+)\s+shares\s+in total may be acquired",
        prose, re.IGNORECASE,
    )
    if m:
        max_shares = int(_parse_number(m.group(1)))

    m = re.search(
        r"during the period\s+(\d{1,2}\s+\w+)\s*(?:–|-|to)\s*(\d{1,2}\s+\w+)",
        prose, re.IGNORECASE,
    )
    if m:
        year = period_end.split("-")[0]
        start_str = _parse_date_english(f"{m.group(1)} {year}")
        end_str = _parse_date_english(f"{m.group(2)} {year}")
        if start_str:
            period_start = start_str
        if end_str:
            period_end = end_str

    return {
        "week_shares": week_shares,
        "week_amount": week_amount,
        "week_avg_price": round(week_avg, 2),
        "acc_shares": acc_shares,
        "acc_amount": 0,
        "acc_holdings": acc_holdings,
        "max_shares": max_shares,
        "period_start": period_start,
        "period_end": period_end,
        "daily_transactions": daily_transactions,
    }


# ============================================================
# The source class
# ============================================================
class NasdaqNewsSource(AnnouncementSource):
    """
    Fetches buyback announcements from Nasdaq Nordic's OAM.

    This is the PRIMARY REGULATORY SOURCE — Nordic listed companies are
    legally required to file their buyback transactions with Nasdaq. The
    same data is distributed via Cision etc., but Nasdaq's own API is:
      1. Public (no auth needed)
      2. Stable (regulatory infrastructure)
      3. Uniform (works for all Nordic companies)

    Args:
        company_name: As it appears in Nasdaq's database (e.g. "Evolution AB")
        uid_prefix: For generating UIDs (e.g. "evo")
        cns_category: Nasdaq's category filter. Default targets buybacks.
        max_listing_pages: How many listing pages to scan (10 per page)
    """

    name = "nasdaq_news"

    # This is the exact string Nasdaq uses for buyback announcements.
    # It's defined in cnsTypeId=6 / categoryId=69 in Nasdaq's taxonomy.
    BUYBACK_CATEGORY = "Changes in company's own shares"

    LISTING_URL = "https://api.news.eu.nasdaq.com/news/query.action"

    def __init__(
        self,
        company_name: str,
        uid_prefix: str,
        cns_category: str = BUYBACK_CATEGORY,
        max_listing_pages: int = 10,
    ):
        self.company_name = company_name
        self.uid_prefix = uid_prefix
        self.cns_category = cns_category
        self.max_listing_pages = max_listing_pages

    # --------------------------------------------------------
    # HTTP helper
    # --------------------------------------------------------
    @staticmethod
    def _fetch(url: str, timeout: int = 20) -> Optional[str]:
        """HTTP GET with browser-like headers. Returns text or None."""
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [nasdaq_news] fetch failed: {url[:80]}... — {e}")
            return None

    # --------------------------------------------------------
    # Listing page → list of release metadata from API
    # --------------------------------------------------------
    def _list_releases(self) -> list[dict]:
        """
        Query Nasdaq News API for this company's buyback releases.
        Filters to English-language versions only (Swedish duplicates skipped).
        Returns newest-first.
        """
        all_items = []
        seen_ids = set()

        for page in range(self.max_listing_pages):
            params = {
                "countResults": "true",
                "globalGroup": "exchangeNotice",
                "displayLanguage": "en",
                "timeZone": "CET",
                "dateMask": "yyyy-MM-dd HH:mm:ss",
                "limit": "10",
                "start": str(page * 10),
                "dir": "DESC",
                "globalName": "NordicAllMarkets",
                "cnsCategory": self.cns_category,
                "company": self.company_name,
                "callback": "handleResponse",
            }
            url = self.LISTING_URL + "?" + urlencode(params)
            response = self._fetch(url)
            if not response:
                break

            # Strip JSONP wrapper: handleResponse({...});
            m = re.match(r'^[^(]*\((.*)\);?\s*$', response, re.DOTALL)
            if not m:
                print(f"  [nasdaq_news] unexpected response format")
                break

            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                print(f"  [nasdaq_news] JSON decode failed: {e}")
                break

            items = data.get("results", {}).get("item", [])
            if not items:
                break

            new_on_page = 0
            for item in items:
                # Skip non-English duplicates (Nasdaq serves sv + en versions)
                if item.get("language") != "en":
                    continue
                disclosure_id = item.get("disclosureId")
                if not disclosure_id or disclosure_id in seen_ids:
                    continue
                seen_ids.add(disclosure_id)
                all_items.append(item)
                new_on_page += 1

            total_count = data.get("count", 0)
            retrieved = (page + 1) * 10
            if retrieved >= total_count:
                break

        return all_items

    # --------------------------------------------------------
    # Fetch fully parsed announcements
    # --------------------------------------------------------
    def fetch_recent(self, max_announcements: int = 50) -> list[Announcement]:
        """Fetch recent buyback announcements. Returns newest-first."""
        print(f"\n[nasdaq_news] Scanning for {self.company_name}...")

        items = self._list_releases()
        print(f"  [nasdaq_news] Found {len(items)} English buyback releases in listings")

        announcements: list[Announcement] = []

        for item in items[:max_announcements]:
            message_url = item.get("messageUrl")
            if not message_url:
                continue

            html = self._fetch(message_url)
            if not html:
                continue

            body = _extract_announcement_body(html)
            if not body:
                print(f"  [nasdaq_news] Could not parse body for {item.get('disclosureId')}")
                continue

            # Announcement date from API (reliable)
            release_time = item.get("releaseTime") or item.get("published", "")
            announcement_date = release_time.split(" ")[0] if release_time else body["period_end"]

            ann = Announcement(
                uid=f"{self.uid_prefix}-nasdaq-{item['disclosureId']}",
                announcement_date=announcement_date,
                source=self.name,
                source_url=message_url,
                period_start=body["period_start"],
                period_end=body["period_end"],
                week_shares=body["week_shares"],
                week_amount=body["week_amount"],
                week_avg_price=body["week_avg_price"],
                acc_shares=body["acc_shares"],
                acc_amount=body["acc_amount"],
                daily_transactions=body["daily_transactions"],
            )
            announcements.append(ann)
            print(
                f"  [nasdaq_news] ✓ {ann.announcement_date}: "
                f"week {ann.week_shares}sh @ {ann.week_avg_price} "
                f"/ acc {ann.acc_shares}sh"
            )

        announcements.sort(key=lambda a: a.announcement_date, reverse=True)
        return announcements

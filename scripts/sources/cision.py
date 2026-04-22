"""
Cision announcement source.

Cision is the primary regulatory news distributor for many Swedish-listed
companies, including Evolution AB, and many others. It's also widely used
across the Nordic region as an alternative to GlobeNewswire.

Listing URL structure:
    https://news.cision.com/{company-slug}
    (plus ?p=2, ?p=3 for pagination)

Each release links to:
    https://news.cision.com/{slug}/r/{release-slug},c{RELEASE_ID}

The release ID `c{RELEASE_ID}` is globally unique and stable — perfect as
our deduplication key.

The transaction table in Evolution's "Acquisitions of own shares" releases
looks like this:

    | Date       | Aggregated daily volume | Weighted average price (SEK) | Daily transaction value (SEK) |
    | 2025-11-17 | 85,000                  | 722.40                       | 61,404,000                    |
    | 2025-11-18 | 92,000                  | 718.20                       | 66,074,400                    |
    | ...        | ...                     | ...                          | ...                           |

Followed by a summary sentence:
    "Since [start_date] up to and including [end_date], a total of X shares
    have been acquired within the scope of the programme. A maximum of Y
    shares in total may be acquired."

This module generalizes — it takes a company slug and keywords, so the
same class works for Evolution, and likely other Cision-distributed
companies. Each company may have slightly different phrasing, configurable
via constructor args.
"""

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import unquote
from urllib.request import urlopen, Request

from .base import Announcement, AnnouncementSource


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# Helpers — numeric / date parsing
# ============================================================
def _parse_number(s):
    """Parse formatted numbers robustly:
        '9,999,890'    → 9999890 (English thousand separator)
        '210.57'       → 210.57  (English decimal)
        '9.999.890'    → 9999890 (European thousand separator, e.g. Danish)
        '210,57'       → 210.57  (European decimal)
        '1,234.56'     → 1234.56 (English)
        '1.234,56'     → 1234.56 (European)
    """
    if not s:
        return 0
    s = str(s).strip()
    s = s.replace("\xa0", "").replace(" ", "")

    n_commas = s.count(",")
    n_periods = s.count(".")

    # Mixed: whichever comes LAST is the decimal, the other is thousand-sep
    if n_commas > 0 and n_periods > 0:
        if s.rfind(",") > s.rfind("."):
            # European: '.'→thousand, ','→decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            # English: ','→thousand, '.'→decimal
            s = s.replace(",", "")
    elif n_commas > 1:
        # Multiple commas, no periods: must be English thousand separator
        s = s.replace(",", "")
    elif n_periods > 1:
        # Multiple periods, no commas: European thousand separator
        s = s.replace(".", "")
    elif n_commas == 1:
        # Single comma: decimal or thousand?
        parts = s.split(",")
        if len(parts[1]) == 3 and parts[1].isdigit() and parts[0].isdigit():
            # Looks like thousand separator (e.g., "92,000")
            s = s.replace(",", "")
        else:
            # Decimal (e.g., "210,57")
            s = s.replace(",", ".")
    # else: single period or no separators — already in float-parseable form

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0


def _parse_date_english(s):
    """
    Parse an English date like '17 November 2025' or '2025-11-17' or
    '17 Nov 2025' → 'YYYY-MM-DD'. Returns None on failure.
    """
    if not s:
        return None
    s = s.strip()

    # ISO format: 2025-11-17
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

    # "17 November 2025" or "17 Nov 2025"
    m = re.match(r"^(\d{1,2})\s+(\w+)\s+(\d{4})$", s)
    if m:
        day, month_name, year = m.groups()
        month = months.get(month_name.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    # "November 17, 2025"
    m = re.match(r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m:
        month_name, day, year = m.groups()
        month = months.get(month_name.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    return None


# ============================================================
# HTML table parser (same as GlobeNewswire/FastEjendom)
# ============================================================
class _TableParser(HTMLParser):
    """Extracts all table rows from an HTML page as list[list[str]]."""
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
# Announcement body parser for Cision releases
# ============================================================
def _extract_announcement_body(html, announcement_date):
    """
    Given the HTML of a Cision "Acquisitions of own shares" release,
    extract the transaction table + metadata.

    Returns a dict with:
        week_shares, week_amount, week_avg_price,
        acc_shares (program-level),
        period_start, period_end,
        daily_transactions

    Returns None if parsing fails.
    """
    parser = _TableParser()
    parser.feed(html)
    rows = parser.rows

    if not rows:
        return None

    # -----------------------------------------------
    # Strategy 1: Look for the transaction table
    # Evolution format:
    #   Row 0: [Date, Aggregated daily volume, Weighted average price (SEK), Daily transaction value (SEK)]
    #   Row 1+: Daily data
    # -----------------------------------------------
    daily_transactions = []
    for row in rows:
        if len(row) < 3:
            continue

        # First cell should be parseable as date
        date_str = _parse_date_english(row[0])
        if not date_str:
            # Try interpreting YYYY-MM-DD at start of first cell
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", row[0].strip())
            if m:
                date_str = m.group(1)

        if not date_str:
            continue

        # Parse remaining columns as shares/price/amount
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

    # Week totals from daily sum
    week_shares = sum(t["shares"] for t in daily_transactions)
    week_amount = sum(t["amount"] for t in daily_transactions)
    week_avg = week_amount / week_shares if week_shares > 0 else 0

    # Period bounds
    dates_sorted = sorted(t["date"] for t in daily_transactions)
    period_start = dates_sorted[0]
    period_end = dates_sorted[-1]

    # -----------------------------------------------
    # Strategy 2: Parse accumulated totals from prose
    # Example text: "Since 24 October 2025 up to and including 21 November 2025,
    # a total of 1,267,038 shares have been acquired within the scope of the programme.
    # A maximum of 20,446,216 shares in total may be acquired."
    # -----------------------------------------------
    # Strip HTML tags for easier parsing
    prose = re.sub(r"<[^>]+>", " ", html)
    prose = re.sub(r"\s+", " ", prose)

    acc_shares = 0
    # Match the acc-shares statement
    m = re.search(
        r"(?:Since|from)\s+\d{1,2}\s+\w+\s+\d{4}\s+"
        r"(?:up to and including\s+\d{1,2}\s+\w+\s+\d{4},?\s+)?"
        r"a total of\s+([\d,\.]+)\s+shares\s+have been acquired",
        prose, re.IGNORECASE,
    )
    if m:
        acc_shares = int(_parse_number(m.group(1)))

    # Fallback: if we didn't find program-level acc, try "holding of own shares"
    # Example: "Following the above acquisitions, Evolution's holding of own
    # shares amounted to 4,884,409 as of 21 November 2025"
    # Note: This is TOTAL company holding, NOT just the program, but useful as fallback
    acc_holdings = 0
    m = re.search(
        r"holding of own shares amount(?:ed|s) to\s+([\d,\.]+)",
        prose, re.IGNORECASE,
    )
    if m:
        acc_holdings = int(_parse_number(m.group(1)))

    # Max shares allowed (programme cap)
    max_shares = 0
    m = re.search(
        r"A maximum of\s+([\d,\.]+)\s+shares\s+in total may be acquired",
        prose, re.IGNORECASE,
    )
    if m:
        max_shares = int(_parse_number(m.group(1)))

    # Extract period from "during the period X – Y"
    m = re.search(
        r"during the period\s+(\d{1,2}\s+\w+)\s*(?:–|-|to)\s*(\d{1,2}\s+\w+)",
        prose, re.IGNORECASE,
    )
    if m:
        # Need to add year — use period_end's year
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
        "acc_shares": acc_shares,  # Program-level total
        "acc_amount": 0,  # Cision releases don't publish acc amount in DKK/SEK
        "acc_holdings": acc_holdings,  # Total company holding (bonus metric)
        "max_shares": max_shares,  # Programme cap
        "period_start": period_start,
        "period_end": period_end,
        "daily_transactions": daily_transactions,
    }


# ============================================================
# The source class
# ============================================================
class CisionSource(AnnouncementSource):
    """
    Fetches buyback announcements from Cision for a given company.

    Args:
        company_slug: The URL slug used by Cision for this company
                      (e.g., "evolution" for Evolution AB).
        uid_prefix: Prefix for generated UIDs (e.g. "evo").
        buyback_keywords: Title substrings that identify buyback releases.
                          Default matches English and Swedish phrasing.
        listing_max_pages: How many paginated listing pages to scan.
                           Default 3 = 30 most recent releases.
    """

    name = "cision"

    DEFAULT_KEYWORDS = (
        "acquisitions of own shares",       # English, used by Evolution
        "acquisition of own shares",        # Singular variant
        "återköp av egna aktier",           # Swedish
        "share buyback transactions",       # Possible English variant
        "share repurchase",                 # Generic English
    )

    # Regex for release URLs in listing page
    # Cision format: /news-release/...,cNNNNNNN or /r/slug,cNNNNNNN
    _RELEASE_URL_RE = re.compile(
        r'href="(/[^/]+/r/[^"]+,c(\d+))"',
        re.IGNORECASE,
    )

    def __init__(
        self,
        company_slug: str,
        uid_prefix: str,
        buyback_keywords: Optional[tuple[str, ...]] = None,
        listing_max_pages: int = 3,
    ):
        self.company_slug = company_slug
        self.uid_prefix = uid_prefix
        self.buyback_keywords = tuple(
            k.lower() for k in (buyback_keywords or self.DEFAULT_KEYWORDS)
        )
        self.listing_max_pages = listing_max_pages

    # --------------------------------------------------------
    # URL construction
    # --------------------------------------------------------
    def _listing_url(self, page: int = 1) -> str:
        """Build the news listing URL for this company."""
        base = f"https://news.cision.com/{self.company_slug}"
        if page > 1:
            return f"{base}?p={page}"
        return base

    @staticmethod
    def _fetch(url: str, timeout: int = 20) -> Optional[str]:
        """HTTP GET with browser-like headers. Returns text or None on error."""
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  [cision] fetch failed: {url} — {e}")
            return None

    # --------------------------------------------------------
    # Listing page → list of release metadata
    # --------------------------------------------------------
    def _list_releases(self) -> list[dict]:
        """
        Scan listing pages and return metadata for buyback releases only.
        """
        found = []
        seen_ids = set()

        for page in range(1, self.listing_max_pages + 1):
            url = self._listing_url(page)
            html = self._fetch(url)
            if not html:
                break

            matches = self._RELEASE_URL_RE.findall(html)
            if not matches:
                break

            # Only keep releases that look like buybacks
            page_found = 0
            for path, rel_id in matches:
                if rel_id in seen_ids:
                    continue

                # Extract title near this URL
                title = self._extract_title_near(html, path)
                if not title:
                    # Fallback: parse slug
                    slug_match = re.search(r"/r/([^,]+),c\d+", path)
                    if slug_match:
                        title = unquote(slug_match.group(1)).replace("-", " ")

                if not self._matches_buyback(title):
                    continue

                seen_ids.add(rel_id)
                found.append({
                    "url": f"https://news.cision.com{path}",
                    "release_id": rel_id,
                    "title": title,
                })
                page_found += 1

            if page_found == 0 and page > 1:
                # No new buyback releases on this page — likely exhausted
                break

        return found

    @staticmethod
    def _extract_title_near(html: str, path: str) -> str:
        """Find anchor text associated with a release URL. Multiple strategies."""
        escaped = re.escape(path)

        # Strategy 1: <a href="{path}">TITLE</a>
        m = re.search(
            rf'<a[^>]+href="{escaped}"[^>]*>\s*([^<]+?)\s*</a>',
            html, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return m.group(1).strip()

        # Strategy 2: URL slug → title
        slug_match = re.search(r"/r/([^,]+),c\d+", path)
        if slug_match:
            return unquote(slug_match.group(1)).replace("-", " ")

        return ""

    def _matches_buyback(self, title: str) -> bool:
        """Check if title is a weekly buyback transaction announcement."""
        if not title:
            return False
        low = title.lower()

        # Must contain a buyback keyword
        if not any(kw in low for kw in self.buyback_keywords):
            return False

        # Exclude: board decisions on NEW programs (no transaction data)
        # "The board of directors of Evolution AB (publ) has resolved on
        # acquisitions of own shares" is a PROGRAM START announcement.
        start_markers = (
            "has resolved on",
            "resolved on acquisitions",
            "board of directors",
            "launches",
            "announces intention",
            "intention to launch",
        )
        if any(marker in low for marker in start_markers):
            return False

        return True

    # --------------------------------------------------------
    # Fetch fully parsed announcements
    # --------------------------------------------------------
    def fetch_recent(self, max_announcements: int = 20) -> list[Announcement]:
        """Fetch recent buyback announcements. Returns newest-first."""
        print(f"\n[cision] Scanning for {self.company_slug}...")

        metadata_list = self._list_releases()
        print(f"  [cision] Found {len(metadata_list)} buyback releases in listings")

        announcements: list[Announcement] = []

        for meta in metadata_list[:max_announcements]:
            html = self._fetch(meta["url"])
            if not html:
                continue

            # Try to get announcement date from release page
            # Cision uses <time> tag or "Published:" prose
            announcement_date = self._extract_release_date(html)

            body = _extract_announcement_body(html, announcement_date)
            if not body:
                print(f"  [cision] Could not parse table in {meta['url']}")
                continue

            # If we still don't have an announcement date, use period_end
            if not announcement_date:
                announcement_date = body["period_end"]

            ann = Announcement(
                uid=f"{self.uid_prefix}-cision-{meta['release_id']}",
                announcement_date=announcement_date,
                source=self.name,
                source_url=meta["url"],
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
                f"  [cision] ✓ {ann.announcement_date}: "
                f"week {ann.week_shares}sh @ {ann.week_avg_price} "
                f"/ acc {ann.acc_shares}sh"
            )

        announcements.sort(key=lambda a: a.announcement_date, reverse=True)
        return announcements

    @staticmethod
    def _extract_release_date(html: str) -> Optional[str]:
        """Extract release publication date from Cision HTML."""
        # Try <time datetime="2025-11-24">
        m = re.search(r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})', html, re.IGNORECASE)
        if m:
            return m.group(1)

        # Try "Published: ..." or "YYYY-MM-DD HH:MM CET" format
        m = re.search(
            r"\b(\d{4}-\d{2}-\d{2})[T\s]\d{2}:\d{2}",
            html,
        )
        if m:
            return m.group(1)

        # Fallback: "Mon, Nov 24, 2025" or similar
        m = re.search(
            r"\b(\w+,\s+)?(\w+\s+\d{1,2},?\s+\d{4})\b",
            html[:2000],
        )
        if m:
            parsed = _parse_date_english(m.group(2).replace(",", ""))
            if parsed:
                return parsed

        return None

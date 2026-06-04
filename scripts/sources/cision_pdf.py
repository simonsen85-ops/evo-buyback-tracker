"""
PDF-based scraper for Evolution AB buyback announcements.

PRIMARY (and only) source. Discovers buyback PDF URLs from
evolution.com/investors/press-releases/ and downloads them directly
from mb.cision.com.

Architecture rationale (first principles):

  The PDF at mb.cision.com/Main/12069/{cision_id}/{attachment_id}.pdf IS
  the authoritative MAR Article 5 regulatory disclosure document.
  Everything else (Cision newsroom HTML, IR website HTML, MarketScreener
  re-publications) is just metadata or rendering wrappers around the
  same PDF.

  evolution.com/investors/press-releases works without bot detection and
  contains direct links to ALL buyback PDFs (Evolution's Cision customer
  ID is 12069). This is the most reliable discovery path.

Schema verified against actual press releases:
  - "during the period DD Month YYYY – DD Month YYYY, acquired a total of N own shares"
  - daily table: ISO date | volume | avg price | transaction value
  - "Following the above acquisitions, Evolution's holding of own shares amounted to N as of DD Month YYYY"
  - "The total number of shares in Evolution is N"
  - "A maximum of N shares in total may be acquired"
  - "Since DD Month up to and including DD Month, a total of N shares have been acquired within the scope of the program(me)"
"""

from __future__ import annotations

import io
import re
import time
from datetime import date
from typing import Optional

import requests

try:
    from .base import Announcement, AnnouncementSource
    from .parsing import parse_buyback_view, parse_iso_date, BUYBACK_HEADLINE_KEYWORDS
except ImportError:
    from base import Announcement, AnnouncementSource  # type: ignore
    from parsing import parse_buyback_view, parse_iso_date, BUYBACK_HEADLINE_KEYWORDS  # type: ignore


# ============================================================
# Constants
# ============================================================

IR_LISTING_URL = "https://www.evolution.com/investors/press-releases/"

# Cision PDF storage. Customer ID 12069 = Evolution AB.
# Example: https://mb.cision.com/Main/12069/4355598/4124311.pdf
#   /Main/{customer_id}/{cision_release_id}/{attachment_id}.pdf
PDF_URL_PATTERN = r"https://mb\.cision\.com/Main/12069/(\d+)/(\d+)\.pdf"

REQUEST_DELAY = 1.0     # be polite — sequential downloads
TIMEOUT = 60            # PDFs can be ~100KB but slow servers

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

LOG_PREFIX = "[cision_pdf]"


# ============================================================
# HTTP helpers
# ============================================================

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_ir_listing(session: Optional[requests.Session] = None) -> Optional[str]:
    """Fetch Evolution's IR press-releases listing HTML."""
    sess = session or _make_session()
    try:
        r = sess.get(IR_LISTING_URL, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  {LOG_PREFIX} IR listing fetch failed: {e}")
        return None


def fetch_pdf_bytes(url: str, session: Optional[requests.Session] = None) -> Optional[bytes]:
    """Download a PDF from mb.cision.com."""
    sess = session or _make_session()
    try:
        r = sess.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        ct = r.headers.get("Content-Type", "")
        if "pdf" not in ct.lower():
            print(f"  {LOG_PREFIX}   warning: {url} returned Content-Type={ct!r}")
        return r.content
    except Exception as e:
        print(f"  {LOG_PREFIX}   PDF fetch failed for {url}: {e}")
        return None


# ============================================================
# IR listing parser
# ============================================================

def extract_pdf_links(html: str) -> list[tuple[str, str, str]]:
    """
    Find all (cision_id, pdf_url, headline) tuples from the IR listing HTML.

    The IR page structure is (verified via curl):
        <a href="https://mb.cision.com/Main/12069/{cision_id}/{attachment_id}.pdf"
           target="_blank" class="h4">HEADLINE</a>

    Returns deduplicated list in document order.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    seen_ids: set[str] = set()
    out: list[tuple[str, str, str]] = []

    for a in soup.find_all("a", href=True):
        m = re.search(PDF_URL_PATTERN, a["href"])
        if not m:
            continue
        cision_id = m.group(1)
        if cision_id in seen_ids:
            continue
        seen_ids.add(cision_id)

        headline = a.get_text(" ", strip=True)
        if not headline:
            headline = a.get("title", "") or a.get("aria-label", "") or ""

        out.append((cision_id, a["href"], headline))

    return out


# ============================================================
# PDF text extraction
# ============================================================

def pdf_to_text(pdf_bytes: bytes) -> Optional[str]:
    """Extract concatenated text from all pages of a PDF."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  {LOG_PREFIX} pypdf not installed — run: pip install pypdf")
        return None

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        chunks = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            chunks.append(txt)
        return "\n".join(chunks)
    except Exception as e:
        print(f"  {LOG_PREFIX}   PDF text extraction failed: {e}")
        return None


# ============================================================
# AnnouncementSource implementation
# ============================================================

class CisionPDFSource(AnnouncementSource):
    """Downloads + parses buyback PDFs from Cision's media bucket."""
    name = "cision_pdf"

    def __init__(
        self,
        uid_prefix: str = "evo",
        programs: Optional[list[dict]] = None,
    ):
        self.uid_prefix = uid_prefix
        self.programs = programs or []

    def _program_for_date(self, d: date) -> Optional[dict]:
        iso = d.isoformat()
        for prog in self.programs:
            start = prog.get("start", "")
            eff_end = prog.get("closed_on") or prog.get("end", "9999-12-31")
            if start <= iso <= eff_end:
                return prog
        return None

    def fetch_recent(self, max_announcements: int = 20) -> list[Announcement]:
        try:
            return self._fetch(max_announcements)
        except Exception as exc:
            print(f"  [{self.name}] fetch failed: {exc}")
            return []

    def _fetch(self, max_announcements: int) -> list[Announcement]:
        session = _make_session()

        print(f"  {LOG_PREFIX} Fetching IR listing: {IR_LISTING_URL}")
        html = fetch_ir_listing(session)
        if not html:
            return []

        all_links = extract_pdf_links(html)
        print(f"  {LOG_PREFIX} Found {len(all_links)} unique press release PDFs")

        # Filter to buyback PDFs by headline
        buyback_links = [
            (cid, url, headline) for cid, url, headline in all_links
            if any(kw in headline.lower() for kw in BUYBACK_HEADLINE_KEYWORDS)
        ]
        print(f"  {LOG_PREFIX} {len(buyback_links)} match buyback headline keywords")

        if not buyback_links:
            return []

        results: list[Announcement] = []
        skipped_pre_program = 0
        skipped_parse_fail = 0

        for cision_id, pdf_url, headline in buyback_links[:max_announcements * 2]:
            if len(results) >= max_announcements:
                break

            time.sleep(REQUEST_DELAY)
            pdf_bytes = fetch_pdf_bytes(pdf_url, session)
            if not pdf_bytes:
                continue

            text = pdf_to_text(pdf_bytes)
            if not text:
                continue

            # Wrap in minimal HTML so parse_buyback_view's BeautifulSoup
            # text extraction works (it normalizes whitespace from the
            # raw PDF text)
            html_wrapped = f"<html><body><pre>{text}</pre></body></html>"
            parsed = parse_buyback_view(html_wrapped)

            if not parsed["period_start"] or not parsed["week_shares"]:
                skipped_parse_fail += 1
                print(f"  {LOG_PREFIX}   c{cision_id}: parse incomplete, skipping")
                continue

            ps = parse_iso_date(parsed["period_start"])
            prog = self._program_for_date(ps) if ps else None
            if self.programs and prog is None:
                skipped_pre_program += 1
                continue

            results.append(Announcement(
                uid=f"{self.uid_prefix}-cision-c{cision_id}",
                announcement_date=parsed["period_end"],
                source=self.name,
                source_url=pdf_url,
                period_start=parsed["period_start"],
                period_end=parsed["period_end"],
                week_shares=parsed["week_shares"],
                week_amount=parsed["week_amount"] or 0,
                week_avg_price=parsed["week_avg_price"] or 0.0,
                acc_shares=parsed["acc_shares"] or parsed["week_shares"],
                acc_amount=0,  # Computed by orchestrator
                treasury_shares=parsed["treasury_shares"],
                total_shares_outstanding=parsed["total_shares_outstanding"],
                max_program_shares=parsed["max_program_shares"],
                program_id=prog.get("id") if prog else None,
                daily_transactions=parsed["daily_transactions"],
                completed=parsed["completed"],
            ))
            print(
                f"  {LOG_PREFIX}   ✓ c{cision_id}: "
                f"{parsed['period_start']}..{parsed['period_end']} "
                f"| {parsed['week_shares']:,} sh "
                f"| treasury={parsed['treasury_shares']:,}"
            )

        if skipped_parse_fail:
            print(f"  {LOG_PREFIX} {skipped_parse_fail} parse failures")
        if skipped_pre_program:
            print(f"  {LOG_PREFIX} {skipped_pre_program} outside configured programs")
        print(f"  {LOG_PREFIX} returning {len(results)} Announcement(s)")
        return results


# ============================================================
# Standalone test
# ============================================================

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Test the Cision PDF scraper for EVO")
    p.add_argument("--max", type=int, default=5, help="Max announcements (default 5)")
    args = p.parse_args()

    src = CisionPDFSource()
    anns = src.fetch_recent(max_announcements=args.max)
    print(f"\nFound {len(anns)} announcement(s):")
    for a in anns:
        print(
            f"  {a.announcement_date} | {a.period_start}..{a.period_end} "
            f"| {a.week_shares:,} sh @ {a.week_avg_price:.2f} = SEK {a.week_amount:,}"
        )

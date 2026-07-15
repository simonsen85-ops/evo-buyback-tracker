"""
Evolution AB HTML scraper (post-MFN migration, July 2026).

Evolution moved from Cision to MFN as their MAR Article 17(2) disclosure agent
in July 2026. This changed:
  - Listing URL:    /investors/press-releases/            → /investors/financial-publications/press-releases/
  - PDF hosting:    mb.cision.com/Main/12069/{id}/...     → storage.mfn.se/{uuid}/{slug}.pdf
  - Cision IDs:     c{numeric_id} slugs                   → text slugs like "acquisitions-of-own-shares-in-evolution-ab-publ-1"

The new detail pages (evolution.com/.../press-releases/{slug}) are 100%
server-rendered with:
  - Full text body containing all regex patterns we already parse
  - HTML <table> with daily transaction data (structured, not text-columns)
  - PDF download link to MFN storage

Advantages over previous PDF-based scraper:
  - No pypdf dependency needed (pure HTML parsing)
  - HTML tables are more robust than text-column extraction
  - Faster (no PDF download step)
  - More resilient to layout changes (server-side rendering is stable)

Source priority:
  (1) Evolution HTML detail pages   ← THIS MODULE (only source now)
  (2) MFN PDFs                       ← Same content, we don't need them
"""

from __future__ import annotations

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

LISTING_URL = "https://www.evolution.com/investors/financial-publications/press-releases"
DETAIL_URL_TPL = "https://www.evolution.com/investors/financial-publications/press-releases/{slug}"

# Press release link pattern on the listing page.
# Matches: /investors/financial-publications/press-releases/{slug}
# where slug is lowercase letters, digits, hyphens (e.g.
# "acquisitions-of-own-shares-in-evolution-ab-publ" or the same with
# numeric ("-1") or hex-hash ("-72528c0f") suffix).
SLUG_PATTERN = r"/investors/financial-publications/press-releases/([a-z0-9][a-z0-9\-]+)"

# MFN PDF pattern (extracted for source_url reference; not used for parsing)
MFN_PDF_PATTERN = r"https://storage\.mfn\.se/([0-9a-f\-]{36})/([a-z0-9\-]+)\.pdf"

REQUEST_DELAY = 1.0
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

LOG_PREFIX = "[evo_html]"


# ============================================================
# HTTP helpers
# ============================================================

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_listing_html(page: int = 1, session: Optional[requests.Session] = None) -> Optional[str]:
    """Fetch Evolution's press releases listing page.

    Page 1 (default) is the URL without query param. Later pages use ?page=N.
    """
    sess = session or _make_session()
    url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
    try:
        r = sess.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        if len(r.text) < 10000:
            print(f"  {LOG_PREFIX} suspiciously short listing response ({len(r.text)} chars)")
        return r.text
    except Exception as e:
        print(f"  {LOG_PREFIX} listing fetch failed for page {page}: {e}")
        return None


def fetch_detail_html(slug: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Fetch a single press release detail page."""
    sess = session or _make_session()
    url = DETAIL_URL_TPL.format(slug=slug)
    try:
        r = sess.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  {LOG_PREFIX}   {slug}: detail fetch failed ({e})")
        return None


# ============================================================
# Listing parser
# ============================================================

def extract_listing_entries(html: str) -> list[tuple[str, str]]:
    """
    Extract (slug, headline) tuples from the listing HTML.

    The listing page is server-rendered with anchors matching:
      <a href="/investors/financial-publications/press-releases/{slug}">
        ...
        <h3>{headline}</h3>
        ...
      </a>

    Returns deduplicated list in document order (newest first as served).
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    entries: list[tuple[str, str]] = []
    seen_slugs: set[str] = set()

    for a in soup.find_all("a", href=True):
        m = re.search(SLUG_PATTERN, a["href"])
        if not m:
            continue
        slug = m.group(1)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Extract headline: prefer <h3> inside anchor; fall back to full text
        h = a.find(["h1", "h2", "h3", "h4"])
        headline = h.get_text(" ", strip=True) if h else a.get_text(" ", strip=True)
        # Trim to first ~200 chars in case anchor contains extra content
        headline = headline[:200] if headline else ""

        entries.append((slug, headline))

    return entries


def extract_pdf_url(detail_html: str) -> Optional[str]:
    """Find the MFN PDF URL in a detail page, if present."""
    m = re.search(MFN_PDF_PATTERN, detail_html)
    return m.group(0) if m else None


# ============================================================
# AnnouncementSource implementation
# ============================================================

class EvolutionHTMLSource(AnnouncementSource):
    """Scrapes Evolution's press releases from evolution.com directly (HTML)."""
    name = "evolution_html"

    def __init__(
        self,
        uid_prefix: str = "evo",
        programs: Optional[list[dict]] = None,
        max_pages: int = 3,
    ):
        self.uid_prefix = uid_prefix
        self.programs = programs or []
        self.max_pages = max_pages  # How many listing pages to scan (10 per page)

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

        # Walk listing pages until we have enough candidates or hit page cap
        all_entries: list[tuple[str, str]] = []
        seen_slugs: set[str] = set()
        for page in range(1, self.max_pages + 1):
            print(f"  {LOG_PREFIX} Fetching listing page {page}")
            html = fetch_listing_html(page, session)
            if not html:
                break
            page_entries = extract_listing_entries(html)
            new_entries = [(s, h) for s, h in page_entries if s not in seen_slugs]
            for s, _ in new_entries:
                seen_slugs.add(s)
            all_entries.extend(new_entries)
            print(f"  {LOG_PREFIX}   page {page}: {len(page_entries)} entries ({len(new_entries)} new)")
            if len(new_entries) == 0:
                break  # No new entries — pagination exhausted or duplicate page

        print(f"  {LOG_PREFIX} Total: {len(all_entries)} unique press releases across pages")

        # Filter to buyback press releases by headline
        buybacks = [
            (slug, headline) for slug, headline in all_entries
            if any(kw in headline.lower() for kw in BUYBACK_HEADLINE_KEYWORDS)
        ]
        print(f"  {LOG_PREFIX} {len(buybacks)} match buyback headline keywords")

        if not buybacks:
            return []

        results: list[Announcement] = []
        skipped_pre_program = 0
        skipped_parse_fail = 0

        for slug, headline in buybacks[: max_announcements * 2]:
            if len(results) >= max_announcements:
                break

            time.sleep(REQUEST_DELAY)
            detail_html = fetch_detail_html(slug, session)
            if not detail_html:
                continue

            parsed = parse_buyback_view(detail_html)
            if not parsed["period_start"] or not parsed["week_shares"]:
                skipped_parse_fail += 1
                print(f"  {LOG_PREFIX}   {slug}: parse incomplete, skipping")
                continue

            ps = parse_iso_date(parsed["period_start"])
            prog = self._program_for_date(ps) if ps else None
            if self.programs and prog is None:
                skipped_pre_program += 1
                continue

            # Prefer MFN PDF URL for source_url (the canonical MAR document)
            # Fall back to the Evolution detail page URL if PDF not found
            pdf_url = extract_pdf_url(detail_html)
            source_url = pdf_url or DETAIL_URL_TPL.format(slug=slug)

            results.append(Announcement(
                uid=f"{self.uid_prefix}-mfn-{slug}",
                announcement_date=parsed["period_end"],
                source=self.name,
                source_url=source_url,
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
                f"  {LOG_PREFIX}   ✓ {slug}: "
                f"{parsed['period_start']}..{parsed['period_end']} "
                f"| {parsed['week_shares']:,} sh "
                f"| treasury={parsed['treasury_shares'] or 0:,}"
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
    p = argparse.ArgumentParser(description="Test the Evolution HTML scraper")
    p.add_argument("--max", type=int, default=5, help="Max announcements (default 5)")
    p.add_argument("--pages", type=int, default=3, help="Max listing pages to scan")
    args = p.parse_args()

    src = EvolutionHTMLSource(max_pages=args.pages)
    anns = src.fetch_recent(max_announcements=args.max)
    print(f"\nFound {len(anns)} announcement(s):")
    for a in anns:
        print(
            f"  {a.announcement_date} | {a.period_start}..{a.period_end} "
            f"| {a.week_shares:,} sh @ {a.week_avg_price:.2f} = SEK {a.week_amount:,}"
        )

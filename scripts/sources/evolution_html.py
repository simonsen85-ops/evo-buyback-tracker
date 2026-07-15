"""
Evolution AB HTML scraper (post-MFN migration, July 2026).

Evolution moved from Cision to MFN as their MAR disclosure agent in July
2026. Press releases now live at:
  evolution.com/investors/financial-publications/press-releases/{slug}
with PDF copies at storage.mfn.se/{uuid}/{slug}.pdf.

Detail pages are fully server-rendered HTML containing all data we need
(text patterns + structured <table> with daily transactions).

DISCOVERY STRATEGY (robust against React frontends):
The listing page may render its cards client-side from an embedded JSON
hydration blob (window.__reactRouterContext) rather than server-rendered
anchors. We therefore extract slugs from the RAW response text with regex,
after normalizing JSON-escaped slashes. This catches slugs regardless of
whether they appear in <a href>, JSON strings, or both.

BUYBACK FILTERING:
The slug itself contains the headline text (e.g.
"acquisitions-of-own-shares-in-evolution-ab-publ-1"), so we filter by slug
prefix instead of parsing listing card headlines.

ENCODING NOTE:
We deliberately do NOT advertise brotli (br) in Accept-Encoding — Python
requests cannot decompress brotli without an extra package, and Evolution's
CDN will happily serve it if offered, yielding undecodable garbage.
"""

from __future__ import annotations

import re
import time
from datetime import date
from typing import Optional

import requests

try:
    from .base import Announcement, AnnouncementSource
    from .parsing import parse_buyback_view, parse_iso_date
except ImportError:
    from base import Announcement, AnnouncementSource  # type: ignore
    from parsing import parse_buyback_view, parse_iso_date  # type: ignore


# ============================================================
# Constants
# ============================================================

LISTING_URL = "https://www.evolution.com/investors/financial-publications/press-releases"
DETAIL_URL_TPL = "https://www.evolution.com/investors/financial-publications/press-releases/{slug}"

# Slug pattern in RAW text (after slash-normalization). Matches both
# href="/investors/..." anchors and "/investors/..." JSON strings.
SLUG_PATTERN = r"/investors/financial-publications/press-releases/([a-z0-9][a-z0-9\-]*)"

# Buyback press releases are identified by slug prefix — the slug IS the
# slugified headline ("Acquisitions of own shares in Evolution AB (publ)").
BUYBACK_SLUG_PREFIXES = (
    "acquisitions-of-own-shares",
    "acquisition-of-own-shares",
    "transactions-in-own-shares",
    "transaction-in-own-shares",
)

# MFN PDF pattern (for source_url reference)
MFN_PDF_PATTERN = r"https://storage\.mfn\.se/([0-9a-f\-]{36})/([a-z0-9\-]+)\.pdf"

REQUEST_DELAY = 1.0
TIMEOUT = 30

# NOTE: no "br" — requests can't decode brotli without extra deps
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
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


def _normalize(text: str) -> str:
    """Normalize JSON-escaped slashes so slug regex matches inside JSON blobs."""
    return text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")


def fetch_listing_html(page: int = 1, session: Optional[requests.Session] = None) -> Optional[str]:
    """Fetch a listing page. Page 1 = bare URL; later pages use ?page=N."""
    sess = session or _make_session()
    url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
    try:
        r = sess.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        print(f"  {LOG_PREFIX}   listing page {page}: HTTP {r.status_code}, "
              f"{len(r.text):,} chars, encoding={r.headers.get('Content-Encoding', 'none')}")
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
# Extraction
# ============================================================

def extract_slugs(html: str) -> list[str]:
    """
    Extract press-release slugs from raw listing HTML.

    Works on both server-rendered anchors and JSON hydration blobs
    (escaped slashes are normalized first). Returns deduplicated slugs
    in first-seen order (page order = newest first).
    """
    text = _normalize(html)
    seen: set[str] = set()
    out: list[str] = []
    for m in re.finditer(SLUG_PATTERN, text):
        slug = m.group(1)
        # Trim trailing punctuation artifacts from JSON contexts
        slug = slug.rstrip("-")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(slug)
    return out


def is_buyback_slug(slug: str) -> bool:
    return any(slug.startswith(p) for p in BUYBACK_SLUG_PREFIXES)


def extract_pdf_url(detail_html: str) -> Optional[str]:
    """Find the MFN PDF URL in a detail page, if present."""
    m = re.search(MFN_PDF_PATTERN, _normalize(detail_html))
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
        self.max_pages = max_pages

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

        all_slugs: list[str] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            print(f"  {LOG_PREFIX} Fetching listing page {page}")
            html = fetch_listing_html(page, session)
            if not html:
                break
            page_slugs = extract_slugs(html)
            new_slugs = [s for s in page_slugs if s not in seen]
            for s in new_slugs:
                seen.add(s)
            all_slugs.extend(new_slugs)
            print(f"  {LOG_PREFIX}   page {page}: {len(page_slugs)} slugs ({len(new_slugs)} new)")
            if not new_slugs:
                break

        print(f"  {LOG_PREFIX} Total: {len(all_slugs)} unique press releases")

        buyback_slugs = [s for s in all_slugs if is_buyback_slug(s)]
        print(f"  {LOG_PREFIX} {len(buyback_slugs)} match buyback slug prefixes")

        if not buyback_slugs:
            # Diagnostic aid: show a sample of what WAS found
            sample = all_slugs[:5]
            if sample:
                print(f"  {LOG_PREFIX} sample slugs found: {sample}")
            return []

        results: list[Announcement] = []
        skipped_pre_program = 0
        skipped_parse_fail = 0

        for slug in buyback_slugs[: max_announcements * 2]:
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
                acc_amount=0,
                treasury_shares=parsed["treasury_shares"],
                total_shares_outstanding=parsed["total_shares_outstanding"],
                max_program_shares=parsed["max_program_shares"],
                program_id=prog.get("id") if prog else None,
                daily_transactions=parsed["daily_transactions"],
                completed=parsed["completed"],
            ))
            print(
                f"  {LOG_PREFIX}   \u2713 {slug}: "
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
    p.add_argument("--max", type=int, default=5)
    p.add_argument("--pages", type=int, default=3)
    args = p.parse_args()

    src = EvolutionHTMLSource(max_pages=args.pages)
    anns = src.fetch_recent(max_announcements=args.max)
    print(f"\nFound {len(anns)} announcement(s):")
    for a in anns:
        print(
            f"  {a.announcement_date} | {a.period_start}..{a.period_end} "
            f"| {a.week_shares:,} sh @ {a.week_avg_price:.2f} = SEK {a.week_amount:,}"
        )

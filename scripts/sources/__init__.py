"""
EVO Buyback Tracker — Source modules

Architecture (mirrors FED and IMB):
- base.py defines the Announcement dataclass + AnnouncementSource ABC
- parsing.py contains shared HTML/text parsers for Evolution press releases
- cision_pdf.py — PRIMARY: downloads buyback PDFs from mb.cision.com

Source rationale (first-principles, verified for EVO):

The PDF at mb.cision.com/Main/12069/{cision_id}/{attachment_id}.pdf IS the
authoritative MAR Article 5 regulatory disclosure document. Everything
else (Cision newsroom HTML, IR website HTML) is just metadata or
rendering wrappers around the same PDF.

evolution.com/investors/press-releases works without bot detection and
contains direct links to ALL buyback PDFs (Evolution's Cision customer
ID is 12069). This is the most reliable discovery path.

Why we don't use Cision HTML (news.cision.com/evolution):
- Cloudflare bot detection sometimes blocks automated fetches
- HTML structure can change without notice
- The PDF is the canonical document anyway

Why we don't use Nasdaq Stockholm news API (api.news.eu.nasdaq.com):
- Only carries issuer reports + market notices, NOT weekly Article 5
  buyback reports (verified empirically — returns 0 buyback items)

Why we don't use Finansinspektionen OAM (finanscentralen.fi.se):
- Primarily for MAR Article 17 inside information + major shareholding
  notifications, not weekly Article 5 buybacks
- ASP.NET form interface with no clean API
"""

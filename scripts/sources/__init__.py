"""
EVO Buyback Tracker — Source modules

Architecture (mirrors FED and IMB):
- base.py defines the Announcement dataclass + AnnouncementSource ABC
- parsing.py contains shared HTML/text parsers for Evolution press releases
- evolution_html.py — PRIMARY: parses evolution.com press release pages

Source history for Evolution AB:
- Until July 2026: Cision was the MAR Article 17(2) disclosure agent.
  PDFs lived at mb.cision.com/Main/12069/{id}/{att}.pdf and the old
  cision_pdf.py module downloaded + parsed them with pypdf.
- From July 2026: Evolution migrated to MFN. Press releases now live at
  evolution.com/investors/financial-publications/press-releases/{slug}
  as fully server-rendered HTML (with PDF copies at storage.mfn.se).
  evolution_html.py parses the HTML directly — no PDF step needed.

Old announcements keep their evo-cision-c{id} UIDs in data.json;
new ones use evo-mfn-{slug}. merge_announcements dedups by UID.
"""

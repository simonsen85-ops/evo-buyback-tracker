# EVO Buyback Tracker — notes for Claude

Share-buyback tracker for Evolution AB (publ) (EVO.ST, Nasdaq Stockholm).
Amounts are in SEK; programme caps are in EUR (`max_eur`).
Live: https://simonsen85-ops.github.io/evo-buyback-tracker/
Owner: Rasmus (Surface Capital). His EVO valuation model gives no credit for
buybacks, so this tracker is where buyback value is judged. Talk to him in
English, in plain language.

## Pipeline

`scripts/scraper.py` → `data.json` → `scripts/build_html.py` → `index.html`.
`index.html` is generated: never edit it by hand.

Workflow `.github/workflows/scrape.yml` runs weekdays 16:30 UTC and on manual
trigger: install requirements → scraper → build_html → commit & push → deploy
via `actions/deploy-pages`. Dependencies: `requests`, `beautifulsoup4`.

## Working from a Claude Code session

- **Commit code, not data.** Don't commit `data.json` or `index.html`: the
  Actions bot commits both to `main` every weekday, so a branch that touches
  them will conflict. Change data through code (migrations in `scraper.py`)
  and let the workflow regenerate both files.
- Work on a branch and open a pull request; Rasmus merges it on GitHub. After
  a merge, the dashboard only changes when the workflow next runs. Tell him to
  run it from the Actions tab if the change should show today.
- **Cloud sessions have a network allowlist.** This repo needs: evolution.com, *.evolution.com, storage.mfn.se, *.nasdaq.com, *.finance.yahoo.com.
  If a fetch fails from a cloud session, check the allowlist before concluding
  that the site or its format has changed.

## Before changing anything

- `git pull --rebase` first. The Actions bot commits every weekday.
- Test parsers offline: save a press-release HTML page as a fixture and run
  `parsing.parse_buyback_view(html)` on it. Open `index.html` locally and check
  for JavaScript errors before pushing.

## Sources (`scripts/sources/`)

Evolution changed its disclosure agent from Cision to MFN in July 2026. That
changed both the listing URL and the PDF hosting.

- `evolution_html.py` — **primary** (MFN era).
  - Listing: `evolution.com/investors/financial-publications/press-releases`.
    The page renders client-side, so slugs are pulled from the raw response
    with a regex after un-escaping JSON slashes.
  - Buybacks are filtered by slug prefix
    (`acquisitions-of-own-shares-in-evolution-ab-publ…`).
  - Detail pages are server-rendered and contain a daily table.
  - Don't advertise brotli in `Accept-Encoding`: `requests` can't decode it and
    the CDN will send it.
- `parsing.py` — `parse_buyback_view(html)`, the shared parser for the weekly
  MAR format:
  - period total ("acquired a total of N own shares")
  - daily table: Date | Volume | Avg price | Value
  - holding statement and total shares
  - max cap and programme accumulator
  - completion flag
- `cision_pdf.py` — legacy Cision-era PDF parser. It is still in the repo but is
  **not imported** by `scraper.py`; ask Rasmus before deleting it.
- `volume/`:
  - `nasdaq.py` — primary volume source (instrument `TX1757078`; its docstring
    still mentions FED from the copy)
  - `yahoo.py` — fallback
  - `compute.py` — Safe Harbour metrics: 25 % of the 20-day average daily volume
- Price: Yahoo `EVO.ST` → `data.current_price`.

## data.json

- `announcements[]` holds one weekly row: `uid`, `announcement_date`,
  `period_start` / `period_end`, `week_shares`, `week_amount` (SEK),
  `week_avg_price`, `acc_*`, `source`, `source_url`, plus volume metrics.
- UIDs: old rows keep `evo-cision-c{id}`, new rows use `evo-mfn-{slug}`.
  `merge_announcements()` dedups by UID only, so the same week arriving from two
  sources would be counted twice. Add an economic-key check (period + shares)
  if a second source is ever re-enabled.
- **Config lives in `scraper.py` constants** and is rewritten into `data.json`
  on every run: `TOTAL_SHARES` (199,226,613), `PROGRAMS`. Edit the constants
  when a programme is announced or closed.
- `recompute_program_accumulators()` rebuilds the accumulated amount per
  programme from the weekly rows in date order.
- Active programme: #4, €2bn, started 2026-05-19, ends no later than
  2027-04-30. The 10 % cap is 19,922,661 shares.

## Known gaps / to check

- **No fail-loud guard.** A press release that fails to parse is skipped without
  failing the run. This is exactly how the IMB tracker went silent for four
  weeks in Oct 2026. First improvement: record parse failures in `data.json`
  and fail the workflow on them, as the IMB repo now does.

"""
EVO Buyback Tracker — Scraper v2
- Henter aktiekurs fra Yahoo Finance (fallback i data.json)
- Scraper Evolution's pressemeddelser for nye buyback-trancher
- HTML'en henter selv live kurs via JavaScript ved pageload

GitHub Actions kører dette dagligt.
"""

import json
import re
import requests
from datetime import datetime, timezone
from pathlib import Path


def fetch_yahoo_price(ticker: str = "EVO.ST") -> dict:
    """Hent seneste kurs fra Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": "5d", "interval": "1d"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": meta.get("currency", "SEK"),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        print(f"Yahoo Finance fejl: {e}")
        return None


def scrape_buyback_releases() -> list:
    """Scrape Evolution's pressemeddelsesside for buyback-trancher."""
    url = "https://www.evolution.com/investors/press-releases/"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"Kunne ikke hente pressemeddelser: {e}")
        return []

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")

    tranches = []
    # Søg i al tekst på siden efter buyback-mønstre
    page_text = soup.get_text()
    
    # Find alle "acquired a total of X own shares" med kontekst
    pattern = r"(?:during the period\s+)(\d{1,2}\s+\w+)\s*[–\-]\s*(\d{1,2}\s+\w+).*?acquired a total of\s+([\d,]+)\s+own shares"
    matches = re.findall(pattern, page_text, re.DOTALL | re.IGNORECASE)

    for start, end, shares_str in matches:
        shares = int(shares_str.replace(",", ""))
        period = f"{start.strip()} – {end.strip()}"
        tranches.append({
            "period": period,
            "shares": shares,
            "eur_spent": None,
            "note": "",
            "source": "auto-scraped",
        })

    print(f"Fandt {len(tranches)} buyback-trancher fra pressemeddelser")
    return tranches


def load_data() -> dict:
    """Indlæs eksisterende data.json."""
    path = Path("data.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return create_default_data()


def create_default_data() -> dict:
    """Opret standard data.json med alle kendte buyback-trancher."""
    return {
        "meta": {
            "company": "Evolution AB (publ)",
            "ticker": "EVO.ST",
            "exchange": "Nasdaq Stockholm",
            "total_shares_issued": 211833204,
            "shares_outstanding": 200840000,
            "last_updated": "",
        },
        "programme": {
            "name": "€500M Tilbagekøbsprogram",
            "announced": "2025-02-10",
            "completed": "2025-12-08",
            "max_eur": 500000000,
            "spent_eur": 500000000,
            "status": "completed",
        },
        "price": {
            "price": 577.00,
            "change": 0,
            "change_pct": 0,
            "currency": "SEK",
            "timestamp": "2026-03-21",
        },
        "tranches": [
            {"period": "Feb–Maj 2025 (2024 AGM)", "shares": 2100081, "eur_spent": 154000000, "note": "Under gammelt mandat"},
            {"period": "15 maj – 30 jun 2025", "shares": 1115392, "eur_spent": 65400000, "note": "Tranche 1 under 2025 AGM"},
            {"period": "1–5 sep 2025", "shares": 377000, "eur_spent": None, "note": ""},
            {"period": "22–25 sep 2025", "shares": 129523, "eur_spent": None, "note": "Pause for Q3-rapport"},
            {"period": "3–7 nov 2025", "shares": 324409, "eur_spent": None, "note": ""},
            {"period": "10–14 nov 2025", "shares": 191629, "eur_spent": None, "note": ""},
            {"period": "17–21 nov 2025", "shares": 432000, "eur_spent": None, "note": ""},
            {"period": "24–28 nov 2025", "shares": 76000, "eur_spent": None, "note": ""},
            {"period": "1–5 dec 2025", "shares": 142000, "eur_spent": None, "note": ""},
            {"period": "8 dec 2025", "shares": 133140, "eur_spent": None, "note": "Program afsluttet"},
        ],
        "capital_allocation_2026": {
            "dividend_proposed": 0,
            "note": "Bestyrelsen anbefaler intet udbytte for 2025",
            "agm_date": "2026-04-24",
            "new_buyback_mandate": "Afventer opdatering",
        },
    }


def merge_tranches(existing: list, scraped: list) -> list:
    """Flet nye scrapede trancher ind — undgå dubletter baseret på antal aktier."""
    existing_shares = {t["shares"] for t in existing}
    new_count = 0

    for tranche in scraped:
        if tranche["shares"] not in existing_shares:
            existing.append(tranche)
            existing_shares.add(tranche["shares"])
            new_count += 1
            print(f"  Ny tranche: {tranche['period']} — {tranche['shares']:,} aktier")

    if new_count == 0:
        print("  Ingen nye trancher fundet")
    return existing


def main():
    data = load_data()

    # 1. Hent seneste kurs (gemmes som fallback)
    price = fetch_yahoo_price()
    if price:
        data["price"] = price
        print(f"Kurs hentet: {price['price']} {price['currency']}")
    else:
        print("Kunne ikke hente kurs — beholder gammel værdi")

    # 2. Scrape nye buyback-trancher
    print("Scraper pressemeddelser...")
    scraped = scrape_buyback_releases()
    if scraped:
        data["tranches"] = merge_tranches(data["tranches"], scraped)

    # 3. Opdater timestamp
    data["meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 4. Gem data.json
    Path("data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("data.json gemt")


if __name__ == "__main__":
    main()

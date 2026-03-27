"""
EVO Buyback Tracker — Scraper
Henter aktiekurs fra Yahoo Finance og opdaterer data.json + index.html.

Buyback-transaktioner vedligeholdes manuelt i data.json,
da Evolution offentliggør dem som Cision PDF'er uden offentligt API.

Kursdata opdateres automatisk via GitHub Actions (ons + fre).
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
        currency = meta.get("currency", "SEK")

        return {
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "currency": currency,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        print(f"Yahoo Finance fejl: {e}")
        return None


def load_data() -> dict:
    """Indlæs eksisterende data.json."""
    path = Path("data.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # Standard-data med kendte buyback-trancher
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
            "value": 577.00,
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


def update_html(data: dict):
    """Opdater kursdata i index.html."""
    path = Path("index.html")
    if not path.exists():
        print("index.html ikke fundet — springer HTML-opdatering over")
        return

    html = path.read_text(encoding="utf-8")
    price_info = data["price"]
    p = price_info["value"]
    c = price_info["change"]
    cp = price_info["change_pct"]
    ts = price_info["timestamp"]

    # Opdater kursvisning
    # Format: SEK xxx,xx
    price_str = f"SEK {p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    html = re.sub(
        r'<span class="price">SEK [\d.,]+</span>',
        f'<span class="price">{price_str}</span>',
        html
    )

    # Opdater kursændring
    sign = "+" if c >= 0 else ""
    change_class = "positive" if c >= 0 else "negative"
    change_str = f"{sign}{c:,.2f} ({sign}{cp:.2f}%)".replace(",", "X").replace(".", ",").replace("X", ".")
    html = re.sub(
        r'<span class="price-change [^"]*">[^<]+</span>',
        f'<span class="price-change {change_class}">{change_str}</span>',
        html
    )

    # Opdater dato
    html = re.sub(
        r'<span class="price-date">[^<]+</span>',
        f'<span class="price-date">{ts}</span>',
        html
    )

    # Opdater footer-dato
    now_str = datetime.now(timezone.utc).strftime("%d. %b %Y")
    html = re.sub(
        r'Sidst opdateret [^·]+·',
        f'Sidst opdateret {now_str} ·',
        html
    )

    path.write_text(html, encoding="utf-8")
    print(f"HTML opdateret: {price_str} ({change_str})")


def main():
    data = load_data()

    # Hent seneste kurs
    price = fetch_yahoo_price()
    if price:
        data["price"] = price
        print(f"Kurs hentet: {price['price']} {price['currency']}")
    else:
        print("Kunne ikke hente kurs — beholder gammel værdi")

    # Opdater timestamp
    data["meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Gem data.json
    Path("data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("data.json gemt")

    # Opdater HTML
    update_html(data)


if __name__ == "__main__":
    main()

"""
PlayStation Store price parser
Fetches prices from the official PS Store API for regions UA, TR, IN, PL
and updates the local SQLite database.

Usage:
  python parser/ps_store_parser.py [--product-id CUSA12345_00] [--all]

PS Store API (unofficial but stable):
  https://store.playstation.com/store/api/chihiro/00_09_000/container/{lang}/{region}/999/{concept_id}
"""
import asyncio
import aiosqlite
import httpx
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.environ.get("DB_PATH", "database/shop.db"))

# ── Region configuration ──────────────────────────────────────────────────────
REGIONS: dict[str, dict] = {
    "UA": {
        "lang": "uk",
        "country": "UA",
        "currency": "UAH",
        "api_base": "https://store.playstation.com/store/api/chihiro/00_09_000/container/uk/UA/999",
    },
    "TR": {
        "lang": "tr",
        "country": "TR",
        "currency": "TRY",
        "api_base": "https://store.playstation.com/store/api/chihiro/00_09_000/container/tr/TR/999",
    },
    "IN": {
        "lang": "en",
        "country": "IN",
        "currency": "INR",
        "api_base": "https://store.playstation.com/store/api/chihiro/00_09_000/container/en/IN/999",
    },
    "PL": {
        "lang": "pl",
        "country": "PL",
        "currency": "PLN",
        "api_base": "https://store.playstation.com/store/api/chihiro/00_09_000/container/pl/PL/999",
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

PRICE_COLUMN = {"UA": "price_uah", "TR": "price_try", "IN": "price_inr", "PL": "price_pln"}


# ── PS Store API helpers ──────────────────────────────────────────────────────

async def fetch_product_price(
    client: httpx.AsyncClient,
    original_id: str,
    region: str,
) -> float | None:
    """
    Fetch the current price of a product from PS Store for a given region.
    Returns the price as a float, or None if unavailable.

    The PS Store chihiro API returns a JSON with 'included' array containing
    offer objects with 'price' field.
    """
    cfg = REGIONS[region]
    url = f"{cfg['api_base']}/{original_id}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Navigate the PS Store response structure
        included = data.get("included", [])
        for item in included:
            attrs = item.get("attributes", {})
            skus = attrs.get("skus", [])
            for sku in skus:
                prices = sku.get("prices", {})
                non_plus = prices.get("non-plus-user", {})
                actual = non_plus.get("actual-price", {})
                amount = actual.get("value")
                if amount is not None:
                    return float(amount) / 100  # PS Store returns cents

        # Fallback: check top-level price
        top = data.get("attributes", {}).get("default-sku", {})
        price_val = top.get("price")
        if price_val is not None:
            return float(price_val) / 100

    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
        print(f"  [WARN] {region} / {original_id}: {e}")

    return None


async def fetch_prices_for_product(
    client: httpx.AsyncClient,
    product_id: int,
    original_id: str,
) -> dict[str, float | None]:
    """Fetch prices from all 4 regions concurrently."""
    tasks = {
        region: fetch_product_price(client, original_id, region)
        for region in REGIONS
    }
    results: dict[str, float | None] = {}
    for region, coro in tasks.items():
        results[region] = await coro
    return results


# ── Database helpers ──────────────────────────────────────────────────────────

async def update_product_prices(
    conn: aiosqlite.Connection,
    product_id: int,
    prices: dict[str, float | None],
) -> None:
    """Update product price columns and write to price_snapshots."""
    set_parts = []
    params: list = []

    for region, price in prices.items():
        if price is None:
            continue
        col = PRICE_COLUMN[region]
        set_parts.append(f"{col} = ?")
        params.append(price)

    if set_parts:
        params.append(product_id)
        await conn.execute(
            f"UPDATE products SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            params,
        )

    # Write snapshots
    snapshots = [
        (product_id, region, price, REGIONS[region]["currency"])
        for region, price in prices.items()
        if price is not None
    ]
    if snapshots:
        await conn.executemany(
            "INSERT INTO price_snapshots (product_id, region, price, currency) VALUES (?,?,?,?)",
            snapshots,
        )
    await conn.commit()


async def get_products_to_parse(
    conn: aiosqlite.Connection,
    original_id: str | None = None,
) -> list[tuple[int, str]]:
    """Return [(product_id, original_id)] rows to process."""
    if original_id:
        rows = await conn.execute_fetchall(
            "SELECT id, original_id FROM products WHERE original_id = ? AND is_active = 1",
            (original_id,),
        )
    else:
        rows = await conn.execute_fetchall(
            "SELECT id, original_id FROM products WHERE original_id IS NOT NULL AND is_active = 1"
        )
    return [(r["id"], r["original_id"]) for r in rows]


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(original_id: str | None, parse_all: bool) -> None:
    if not parse_all and not original_id:
        print("Provide --product-id or --all")
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")

        products = await get_products_to_parse(conn, original_id)
        if not products:
            print("No products found to parse.")
            return

        print(f"[+] Parsing {len(products)} product(s)…")
        async with httpx.AsyncClient() as client:
            for pid, oid in products:
                print(f"  → {oid} (db id={pid})")
                prices = await fetch_prices_for_product(client, pid, oid)
                for region, price in prices.items():
                    print(f"     {region}: {price}")
                await update_product_prices(conn, pid, prices)

    print(f"\n✅ Done at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PS Store price parser")
    parser.add_argument("--product-id", help="PS Store original_id to parse (e.g. CUSA34575_00)")
    parser.add_argument("--all", action="store_true", help="Parse all products in DB")
    args = parser.parse_args()
    asyncio.run(run(args.product_id, args.all))


if __name__ == "__main__":
    main()

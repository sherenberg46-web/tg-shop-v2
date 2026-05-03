"""
Spring Sale Import
==================
Fetches covers + prices for sale games from PS Store API (all 4 regions),
saves them to the DB with discount_pct and discount_until fields.

Usage:
    python parser/sale_import.py
"""

import asyncio
import logging
import os
import sqlite3
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from ps_parser import (
    HEADERS, REGIONS,
    fetch_region, find_best_match, get_or_create_category,
    parse_price, pick_cover, normalize,
)

# ── Config ────────────────────────────────────────────────────────
DB_PATH    = Path(os.environ.get("DB_PATH", "database/shop.db"))
SALE_UNTIL = "2025-05-31 23:59:59"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sale_import")

# ── Sale games list ───────────────────────────────────────────────
# (search_query, display_title, platform, discount_pct)
SALE_GAMES: list[tuple[str, str, str, int]] = [
    # ── Page 1 ──────────────────────────────────────────────────
    ("Farming Simulator 25",
     "Farming Simulator 25",                "PS5",      20),
    ("RIDE 6",
     "RIDE 6",                              "PS5",      20),
    ("Clair Obscur Expedition 33",
     "Clair Obscur: Expedition 33",         "PS5",      20),
    ("Avowed",
     "Avowed",                              "PS5",      30),
    ("WWE 2K26",
     "WWE 2K26",                            "PS5",      15),
    ("Poppy Playtime Chapter 4",
     "Poppy Playtime: Глава 4",             "PS4/PS5",  50),
    ("Poppy Playtime Chapter 3",
     "Poppy Playtime: Глава 3",             "PS4/PS5",  50),
    ("Ready or Not",
     "Ready or Not",                        "PS5",      25),
    ("Call of Duty Black Ops 6",
     "Call of Duty: Black Ops 6",           "PS4/PS5",  35),
    ("Grand Theft Auto V",
     "Grand Theft Auto V",                  "PS4/PS5",  67),
    ("Resident Evil 2 Remake",
     "Resident Evil 2",                     "PS4/PS5",  75),
    ("Call of Duty Modern Warfare 2019",
     "Call of Duty: Modern Warfare",        "PS4",      67),
    ("Resident Evil 4 Remake",
     "Resident Evil 4",                     "PS4/PS5",  60),
    ("Phasmophobia",
     "Phasmophobia",                        "PS5",      30),
    ("ARC Raiders",
     "ARC Raiders",                         "PS5",      20),
    # ── Page 2 ──────────────────────────────────────────────────
    ("Resident Evil 7 biohazard",
     "Resident Evil 7: Biohazard",          "PS4/PS5",  60),
    ("Battlefield 6",
     "Battlefield 6",                       "PS5",      25),
    ("Palworld",
     "Palworld",                            "PS5",      25),
    ("No Man Sky",
     "No Man's Sky",                        "PS4/PS5",  60),
    ("Horizon Zero Dawn Remastered",
     "Horizon Zero Dawn Remastered",        "PS5",      50),
    ("Football Manager 2026",
     "Football Manager 26",                 "PS5",      40),
    ("Jurassic World Evolution 3",
     "Jurassic World Evolution 3",          "PS5",      30),
    ("Wobbly Life",
     "Wobbly Life",                         "PS4/PS5",  30),
    ("Rust Console Edition",
     "Rust Console Edition",                "PS5",      35),
    ("Monster Hunter Wilds",
     "Monster Hunter Wilds",                "PS5",      50),
    # ── Page 3 ──────────────────────────────────────────────────
    ("Forza Horizon 5",
     "Forza Horizon 5",                     "PS5",      40),
    ("Grounded",
     "Grounded",                            "PS4/PS5",  50),
    ("REMATCH football",
     "REMATCH",                             "PS5",      40),
    ("Resident Evil Village",
     "Resident Evil Village",               "PS4/PS5",  75),
    ("Kingdom Come Deliverance 2",
     "Kingdom Come: Deliverance II",        "PS5",      50),
    ("Horizon Forbidden West",
     "Horizon Forbidden West",              "PS5",      29),
    ("Little Nightmares 3",
     "Little Nightmares III",               "PS4/PS5",  30),
    ("Fallout 4",
     "Fallout 4",                           "PS4/PS5",  60),
]


# ── DB helpers ────────────────────────────────────────────────────

def upsert_sale_product(conn: sqlite3.Connection, data: dict) -> int:
    """
    Insert or update a product with sale discount.
    Searches by normalized title across ALL active products to avoid dupes.
    """
    title_norm = normalize(data["title"])

    rows = conn.execute(
        "SELECT id, title FROM products WHERE is_active = 1"
    ).fetchall()

    existing_id = None
    for row in rows:
        if normalize(row[1]) == title_norm:
            existing_id = row[0]
            break

    if existing_id:
        conn.execute(
            """UPDATE products SET
                price_uah     = COALESCE(?, price_uah),
                price_try     = COALESCE(?, price_try),
                price_inr     = COALESCE(?, price_inr),
                price_pln     = COALESCE(?, price_pln),
                image_url     = COALESCE(?, image_url),
                platform      = ?,
                discount_pct  = ?,
                discount_until = ?,
                is_featured   = 1,
                is_active     = 1,
                updated_at    = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (
                data.get("price_uah"), data.get("price_try"),
                data.get("price_inr"), data.get("price_pln"),
                data.get("image_url"),
                data["platform"],
                data["discount_pct"],
                data["discount_until"],
                existing_id,
            ),
        )
        conn.commit()
        log.info("  ✔ updated  id=%-4d  %s", existing_id, data["title"])
        return existing_id

    cur = conn.execute(
        """INSERT INTO products
           (category_id, title, description, image_url,
            price_uah, price_try, price_inr, price_pln,
            platform, rating, is_featured, is_active,
            discount_pct, discount_until)
           VALUES (?,?,?,?,?,?,?,?,?,?,1,1,?,?)""",
        (
            data["category_id"],
            data["title"],
            data.get("description", "Игра из весенней распродажи PS Store."),
            data.get("image_url"),
            data.get("price_uah"), data.get("price_try"),
            data.get("price_inr"), data.get("price_pln"),
            data["platform"],
            4.3,
            data["discount_pct"],
            data["discount_until"],
        ),
    )
    conn.commit()
    pid = cur.lastrowid
    log.info("  ✚ inserted id=%-4d  %s", pid, data["title"])
    return pid


# ── Core import logic ─────────────────────────────────────────────

async def import_game(
    client: httpx.AsyncClient,
    query: str,
    display_title: str,
    platform: str,
    discount_pct: int,
    conn: sqlite3.Connection,
) -> None:
    log.info("→ %s  (-%d%%)", display_title, discount_pct)

    # Fetch all 4 regions concurrently
    results = await asyncio.gather(
        *[fetch_region(client, query, r) for r in REGIONS],
        return_exceptions=True,
    )
    region_items = dict(zip(REGIONS.keys(), results))

    # Primary metadata from UA region
    ua_items = region_items.get("UA")
    if isinstance(ua_items, Exception):
        ua_items = []
    primary = find_best_match(ua_items or [], query)

    # Fallback to other regions for cover
    if not primary:
        for r in ["TR", "PL", "IN"]:
            items = region_items.get(r)
            if isinstance(items, list) and items:
                primary = find_best_match(items, query)
                if primary:
                    log.info("  fallback cover from %s", r)
                    break

    cover = pick_cover(primary.get("images", [])) if primary else None

    # Collect prices from each region
    prices: dict[str, float | None] = {}
    for region_code, items in region_items.items():
        if isinstance(items, Exception) or not items:
            prices[region_code] = None
            continue
        match = find_best_match(items, query)
        if match:
            sku = match.get("default_sku", {})
            prices[region_code] = parse_price(sku, region_code)
        else:
            prices[region_code] = None

    found_prices = {k: v for k, v in prices.items() if v}
    if not found_prices and not cover:
        log.warning("  ✗ no data — skipping '%s'", display_title)
        return

    log.info("  prices: %s  cover: %s", found_prices, bool(cover))

    cat_id = get_or_create_category(conn, "ps-games")

    upsert_sale_product(conn, {
        "category_id":   cat_id,
        "title":         display_title,
        "description":   "Игра из весенней распродажи PS Store. Цены актуальны апрель–май 2025.",
        "image_url":     cover,
        "price_uah":     prices.get("UA"),
        "price_try":     prices.get("TR"),
        "price_inr":     prices.get("IN"),
        "price_pln":     prices.get("PL"),
        "platform":      platform,
        "discount_pct":  discount_pct,
        "discount_until": SALE_UNTIL,
    })


async def run() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    log.info("Starting spring sale import: %d games", len(SALE_GAMES))

    async with httpx.AsyncClient(verify=False) as client:
        for query, title, platform, discount_pct in SALE_GAMES:
            await import_game(client, query, title, platform, discount_pct, conn)
            await asyncio.sleep(0.7)

    total = conn.execute(
        "SELECT COUNT(*) FROM products WHERE discount_pct > 0"
    ).fetchone()[0]
    log.info("Done. %d products with active discounts in DB.", total)
    conn.close()


if __name__ == "__main__":
    asyncio.run(run())

"""
PlayStation Store Price Parser
================================
Fetches real game data (prices, covers, metadata) from the official
PlayStation Store API for regions: UA, TR, IN, PL.

Usage:
  python parser/ps_parser.py --run-once
  python parser/ps_parser.py --daemon          # run now + every 6 h
  python parser/ps_parser.py --search "Elden"  # specific game
"""

import argparse
import asyncio
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import httpx
import schedule
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH   = Path(os.environ.get("DB_PATH", "database/shop.db"))
LOG_LEVEL = logging.DEBUG if os.environ.get("DEBUG") == "true" else logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ps_parser")

# ── Region config ─────────────────────────────────────────────────────────────
# divisor: how to convert raw API price to major currency unit
# UA/TR/PL: prices in minor units (kopecks/kurus/grosz) → divide by 100
# IN: prices already in rupees                           → divisor = 1
REGIONS = {
    "UA": {"country": "UA", "lang": "ru", "currency": "UAH", "divisor": 100},
    "TR": {"country": "TR", "lang": "tr", "currency": "TRY", "divisor": 100},
    "IN": {"country": "IN", "lang": "en", "currency": "INR", "divisor": 1},
    "PL": {"country": "PL", "lang": "pl", "currency": "PLN", "divisor": 100},
}

SEARCH_URL = (
    "https://store.playstation.com/store/api/chihiro/00_09_000/tumbler"
    "/{country}/{lang}/999/{query}?suggested_size={size}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://store.playstation.com",
    "Referer": "https://store.playstation.com/",
}

# PS Store image type priorities
# 10 = Portrait cover art (best for 3:4 product cards)
# 1  = Landscape thumbnail
# 12 = Marketing image
PREFERRED_IMAGE_TYPES = [10, 1, 12, 13, 2]


# ── Image helpers ─────────────────────────────────────────────────────────────

def pick_cover(images: list[dict]) -> str | None:
    if not images:
        return None
    by_type: dict[int, str] = {}
    for img in images:
        t = img.get("type", 0)
        url = img.get("url", "")
        if url:
            by_type[t] = url
    for t in PREFERRED_IMAGE_TYPES:
        if t in by_type:
            return by_type[t]
    return images[0].get("url")


# ── Price helpers ─────────────────────────────────────────────────────────────

def parse_price(sku: dict, region: str) -> float | None:
    """Extract price from PS Store SKU with correct region divisor."""
    divisor = REGIONS[region]["divisor"]

    # Primary: numeric price field
    price_raw = sku.get("price")
    if price_raw is not None and isinstance(price_raw, (int, float)) and price_raw > 0:
        return round(price_raw / divisor, 2)

    # Fallback: parse display_price string ("UAH 649,00" / "Rs 1,749" / "₺89,00")
    display = sku.get("display_price", "")
    # Remove currency symbols and whitespace, keep digits, comma, dot
    cleaned = re.sub(r"[^\d,\.]", "", display.replace("\xa0", ""))
    # Treat comma as thousands separator: "1,299" → "1299"; "649,00" → "649.00"
    # Heuristic: if comma is followed by exactly 2 digits at end → decimal separator
    if re.search(r",\d{2}$", cleaned):
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        val = float(cleaned)
        if val > 0:
            return round(val / divisor if divisor > 1 else val, 2)
    except (ValueError, TypeError):
        pass
    return None


# ── Name helpers ──────────────────────────────────────────────────────────────

def clean_name(raw: str) -> str:
    """Remove control chars, trademark symbols, extra whitespace."""
    name = str(raw)
    name = name.replace("\xa0", " ").replace("®", "").replace("™", "").replace("\x00", "")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", clean_name(name).lower())


def find_best_match(items: list[dict], target: str) -> dict | None:
    target_norm = normalize(target)
    target_words = set(target_norm.split())

    scored: list[tuple[int, dict]] = []
    for item in items:
        item_name  = normalize(item.get("name", ""))
        item_words = set(item_name.split())

        if item_name == target_norm:
            return item  # exact match → immediate return

        common = target_words & item_words
        score  = len(common)
        # Bonus if all target words are present
        if common == target_words:
            score += 10
        if score > 0:
            scored.append((score, item))

    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def title_case(name: str) -> str:
    """Proper title case with smart lowercasing of small words."""
    small = {"a", "an", "the", "of", "and", "or", "for", "in", "on", "at", "to"}
    words = name.split()
    result = []
    for i, w in enumerate(words):
        if i == 0 or w.lower() not in small:
            result.append(w.capitalize())
        else:
            result.append(w.lower())
    return " ".join(result)


# ── Async fetch ───────────────────────────────────────────────────────────────

async def fetch_region(
    client: httpx.AsyncClient,
    query: str,
    region_code: str,
    size: int = 30,
) -> list[dict]:
    cfg = REGIONS[region_code]
    url = SEARCH_URL.format(
        country=cfg["country"],
        lang=cfg["lang"],
        query=query.replace(" ", "+"),
        size=size,
    )
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        links = resp.json().get("links", [])
        log.debug("  %s: %d results for '%s'", region_code, len(links), query)
        return links
    except Exception as e:
        log.warning("  [WARN] %s/'%s': %s", region_code, query, e)
        return []


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_or_create_category(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
    if row:
        return row[0]
    cat_map = {
        "ps-games":   ("PlayStation Games", "🎮", 1),
        "ps-plus":    ("PS Plus",           "⭐", 2),
        "gift-cards": ("Gift Cards",        "💳", 3),
        "dlc":        ("DLC & Add-ons",     "🧩", 4),
        "currency":   ("In-Game Currency",  "💰", 5),
    }
    name, icon, order = cat_map.get(slug, (slug, "📦", 99))
    conn.execute(
        "INSERT OR IGNORE INTO categories (name, slug, icon, sort_order) VALUES (?,?,?,?)",
        (name, slug, icon, order),
    )
    conn.commit()
    return conn.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()[0]


def upsert_product(conn: sqlite3.Connection, data: dict) -> int:
    """Insert or update a product matched by normalized title + category."""
    title      = data["title"]
    title_norm = normalize(title)
    cat_id     = data["category_id"]

    # Try normalized title match (handles encoding differences)
    rows = conn.execute(
        "SELECT id, title FROM products WHERE category_id = ?", (cat_id,)
    ).fetchall()
    existing_id = None
    for row in rows:
        if normalize(row[1]) == title_norm:
            existing_id = row[0]
            break

    if existing_id:
        cols, vals = [], []
        for col in ["price_uah", "price_try", "price_inr", "price_pln",
                    "image_url", "platform", "is_featured", "description"]:
            if data.get(col) is not None:
                cols.append(f"{col} = ?")
                vals.append(data[col])
        if cols:
            vals.append(existing_id)
            conn.execute(
                f"UPDATE products SET {', '.join(cols)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                vals,
            )
        conn.commit()
        log.debug("  updated id=%d '%s'", existing_id, title)
        return existing_id

    cur = conn.execute(
        """INSERT INTO products
           (category_id, title, description, image_url,
            price_uah, price_try, price_inr, price_pln,
            platform, rating, is_featured, is_active)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
        (
            cat_id,
            title,
            data.get("description", ""),
            data.get("image_url"),
            data.get("price_uah"),
            data.get("price_try"),
            data.get("price_inr"),
            data.get("price_pln"),
            data.get("platform", "PS"),
            data.get("rating", 4.5),
            int(data.get("is_featured", 0)),
        ),
    )
    conn.commit()
    pid = cur.lastrowid
    log.debug("  inserted id=%d '%s'", pid, title)
    return pid


def save_snapshot(conn: sqlite3.Connection, pid: int, region: str, price: float) -> None:
    conn.execute(
        "INSERT INTO price_snapshots (product_id, region, price, currency) VALUES (?,?,?,?)",
        (pid, region, price, REGIONS[region]["currency"]),
    )
    conn.commit()


# ── Games catalog ─────────────────────────────────────────────────────────────
# (ps_store_query, category_slug, is_featured, display_title_override)
GAME_CATALOG: list[tuple[str, str, bool, str | None]] = [
    # AAA Games
    ("God of War Ragnarok",            "ps-games", True,  "God of War Ragnarök"),
    ("Marvel Spider-Man 2",            "ps-games", True,  "Marvel's Spider-Man 2"),
    ("Elden Ring Shadow Erdtree",       "ps-games", True,  "Elden Ring – Shadow of the Erdtree"),
    ("The Last of Us Part I",          "ps-games", True,  "The Last of Us Part I"),
    ("Resident Evil 4 Remake",         "ps-games", True,  "Resident Evil 4 Remake"),
    ("hogwarts",                        "ps-games", True,  "Hogwarts Legacy"),
    ("EA Sports FC 25",                "ps-games", False, "EA Sports FC 25"),
    ("Cyberpunk 2077 Ultimate Edition","ps-games", False, "Cyberpunk 2077: Ultimate Edition"),
    ("Red Dead Redemption 2",          "ps-games", False, None),
    ("Grand Theft Auto V Premium",     "ps-games", False, "Grand Theft Auto V"),
    # PS Plus
    ("PlayStation Plus Essential",     "ps-plus",  True,  "PS Plus Essential – 1 месяц"),
    ("PlayStation Plus Extra 3",       "ps-plus",  False, "PS Plus Extra – 3 месяца"),
]


# ── Core parse logic ──────────────────────────────────────────────────────────

async def parse_one(
    client: httpx.AsyncClient,
    query: str,
    category_slug: str,
    is_featured: bool,
    title_override: str | None,
    conn: sqlite3.Connection,
) -> None:
    log.info("Parsing: %s", query)

    # Fetch all 4 regions concurrently
    results = await asyncio.gather(
        *[fetch_region(client, query, r) for r in REGIONS],
        return_exceptions=True,
    )
    region_items = dict(zip(REGIONS.keys(), results))

    # Use UA for primary metadata (name, cover, platform)
    ua_items = region_items.get("UA")
    if isinstance(ua_items, Exception) or not ua_items:
        ua_items = []
    primary = find_best_match(ua_items, query)

    if not primary:
        log.warning("  No UA match for '%s'", query)
        # Try to use any region's data
        for r in ["TR", "PL", "IN"]:
            items = region_items.get(r)
            if isinstance(items, list) and items:
                primary = find_best_match(items, query)
                if primary:
                    log.info("  Fallback to %s match", r)
                    break
    if not primary:
        log.warning("  Skipping '%s' — no match in any region", query)
        return

    raw_name = primary.get("name", query)
    title    = title_override or title_case(clean_name(raw_name))
    cover    = pick_cover(primary.get("images", []))
    platform = ", ".join(
        p.replace("\xa0", "").replace("®", "").strip()
        for p in primary.get("playable_platform", [])
        if p.strip()
    ) or "PS"

    # Collect prices
    prices: dict[str, float | None] = {}
    for region_code, items in region_items.items():
        if isinstance(items, Exception) or not items:
            prices[region_code] = None
            continue
        match = find_best_match(items, query)
        if match:
            sku   = match.get("default_sku", {})
            price = parse_price(sku, region_code)
            prices[region_code] = price
            log.info("  %s: %s %s", region_code, price, REGIONS[region_code]["currency"])
        else:
            prices[region_code] = None

    if not any(prices.values()):
        log.warning("  No prices for '%s' — skipping", query)
        return

    cat_id = get_or_create_category(conn, category_slug)
    product_data = {
        "category_id": cat_id,
        "title":       title,
        "description": f"Официальная цифровая версия. Регион: UA/TR/IN/PL.",
        "image_url":   cover,
        "price_uah":   prices.get("UA"),
        "price_try":   prices.get("TR"),
        "price_inr":   prices.get("IN"),
        "price_pln":   prices.get("PL"),
        "platform":    platform,
        "rating":      4.7 if is_featured else 4.3,
        "is_featured": is_featured,
    }

    pid = upsert_product(conn, product_data)
    for region_code, price in prices.items():
        if price is not None:
            save_snapshot(conn, pid, region_code, price)

    log.info("  OK: '%s' id=%d img=%s", title, pid, bool(cover))


async def run_parser(query_filter: str | None = None) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    catalog = GAME_CATALOG
    if query_filter:
        catalog = [
            (q, c, f, t) for q, c, f, t in catalog
            if query_filter.lower() in q.lower() or
               (t and query_filter.lower() in t.lower())
        ]
        if not catalog:
            log.warning("No games matched filter '%s'", query_filter)
            conn.close()
            return

    log.info("Parser starting: %d titles x %d regions", len(catalog), len(REGIONS))

    async with httpx.AsyncClient(verify=False) as client:
        for query, cat_slug, is_featured, title_override in catalog:
            await parse_one(client, query, cat_slug, is_featured, title_override, conn)
            await asyncio.sleep(0.8)  # polite delay

    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    log.info("Done. DB now has %d products. %s",
             count, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    conn.close()


def run_once(query_filter: str | None = None) -> None:
    asyncio.run(run_parser(query_filter))


def run_daemon() -> None:
    log.info("Daemon mode: running now, then every 6 hours")
    run_once()
    schedule.every(6).hours.do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser(description="PS Store price parser")
    parser.add_argument("--run-once",  action="store_true", help="Fetch all games once and exit")
    parser.add_argument("--daemon",    action="store_true", help="Run now, then every 6 h")
    parser.add_argument("--schedule",  action="store_true", help="Only schedule, no immediate run")
    parser.add_argument("--search",    type=str,            help="Filter games by name")
    args = parser.parse_args()

    if args.daemon:
        run_daemon()
    elif args.schedule:
        schedule.every(6).hours.do(run_once, args.search)
        log.info("Scheduled (first run in 6 h). Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_once(args.search)


if __name__ == "__main__":
    main()

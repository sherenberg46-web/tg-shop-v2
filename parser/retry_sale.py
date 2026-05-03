# -*- coding: utf-8 -*-
import asyncio, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from ps_parser import fetch_region, find_best_match, pick_cover, parse_price, normalize, get_or_create_category, REGIONS
import httpx, os
from dotenv import load_dotenv
load_dotenv()

DB_PATH    = Path(os.environ.get("DB_PATH", "database/shop.db"))
SALE_UNTIL = "2025-05-31 23:59:59"

RETRY = [
    ("Resident Evil 4 PS5",   "Resident Evil 4",             "PS4/PS5", 60),
    ("No Mans Sky PS4",       "No Man's Sky",                "PS4/PS5", 60),
    ("REMATCH PS5",           "REMATCH",                     "PS5",     40),
    ("Call of Duty MW 2019",  "Call of Duty: Modern Warfare","PS4",     67),
]

def upsert(conn, data):
    title_norm = normalize(data["title"])
    rows = conn.execute("SELECT id, title FROM products WHERE is_active=1").fetchall()
    for row in rows:
        if normalize(row[1]) == title_norm:
            conn.execute("""UPDATE products SET price_uah=COALESCE(?,price_uah),
                price_try=COALESCE(?,price_try), price_inr=COALESCE(?,price_inr),
                price_pln=COALESCE(?,price_pln), image_url=COALESCE(?,image_url),
                discount_pct=?, discount_until=?, is_featured=1,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (data.get("price_uah"), data.get("price_try"), data.get("price_inr"),
                 data.get("price_pln"), data.get("image_url"),
                 data["discount_pct"], data["discount_until"], row[0]))
            conn.commit()
            print("updated", row[0], data["title"])
            return row[0]
    cur = conn.execute("""INSERT INTO products (category_id,title,description,image_url,
        price_uah,price_try,price_inr,price_pln,platform,rating,is_featured,is_active,
        discount_pct,discount_until) VALUES (?,?,?,?,?,?,?,?,?,?,1,1,?,?)""",
        (data["category_id"], data["title"],
         "Sale game from PS Store spring sale.",
         data.get("image_url"), data.get("price_uah"), data.get("price_try"),
         data.get("price_inr"), data.get("price_pln"), data["platform"], 4.3,
         data["discount_pct"], data["discount_until"]))
    conn.commit()
    print("inserted", cur.lastrowid, data["title"])
    return cur.lastrowid

async def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    async with httpx.AsyncClient(verify=False) as client:
        for query, title, platform, pct in RETRY:
            print("processing:", title)
            results = await asyncio.gather(*[fetch_region(client, query, r) for r in REGIONS], return_exceptions=True)
            region_items = dict(zip(REGIONS.keys(), results))
            ua = region_items.get("UA")
            if isinstance(ua, Exception): ua = []
            primary = find_best_match(ua or [], query)
            if not primary:
                for r in ["TR","PL","IN"]:
                    it = region_items.get(r)
                    if isinstance(it,list) and it:
                        primary = find_best_match(it, query)
                        if primary: break
            cover  = pick_cover(primary.get("images",[])) if primary else None
            prices = {}
            for rc, items in region_items.items():
                if isinstance(items, Exception) or not items: prices[rc]=None; continue
                m = find_best_match(items, query)
                prices[rc] = parse_price(m.get("default_sku",{}), rc) if m else None
            found = {k:v for k,v in prices.items() if v}
            print("  prices:", found, " cover:", bool(cover))
            if not found and not cover:
                print("  SKIP - no data")
                continue
            cat_id = get_or_create_category(conn, "ps-games")
            upsert(conn, {"category_id":cat_id, "title":title, "platform":platform,
                "image_url":cover, "price_uah":prices.get("UA"), "price_try":prices.get("TR"),
                "price_inr":prices.get("IN"), "price_pln":prices.get("PL"),
                "discount_pct":pct, "discount_until":SALE_UNTIL})
            await asyncio.sleep(0.7)
    total = conn.execute("SELECT COUNT(*) FROM products WHERE discount_pct>0").fetchone()[0]
    print("Total with discounts:", total)
    conn.close()

asyncio.run(run())

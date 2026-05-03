"""
Fetch game editions from PS Store product pages for existing products.

Iterates over products with has_editions=0 and tries to extract
edition data (Standard / Deluxe / Ultimate etc.) by fetching the
individual product HTML page and reading __NEXT_DATA__ JSON.

Each product with 2+ editions gets its game_editions rows written
and has_editions=1 set on the parent product.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import aiosqlite

from parser.config import get_price_settings, calc_price_byn
from parser.db import get_connection

log = logging.getLogger(__name__)

CONCURRENCY = 3   # max simultaneous PS Store page requests
REQUEST_DELAY = 0.5  # seconds between requests inside a semaphore slot

_BASE_URLS = {
    "UA": "https://store.playstation.com/ru-ua",
    "TR": "https://store.playstation.com/tr-tr",
}


async def fetch_editions_task(region: str = "ALL") -> AsyncIterator[str]:
    """
    Async generator — yields log strings for SSE streaming.

    region: "UA" | "TR" | "ALL"
    """
    from parser.parsers.ua_parser import UAParser
    from parser.parsers.tr_parser import TrParser

    regions = ["UA", "TR"] if region == "ALL" else [region.upper()]

    conn = await get_connection()
    grand_updated = grand_errors = 0

    try:
        for rgn in regions:
            base_url  = _BASE_URLS[rgn]
            ParserCls = UAParser if rgn == "UA" else TrParser

            # Products that have no editions yet and have a PS Store product ID
            async with conn.execute(
                """SELECT id, title, original_id
                   FROM products
                   WHERE region = ?
                     AND is_active = 1
                     AND product_type = 'game'
                     AND has_editions = 0
                     AND original_id IS NOT NULL
                     AND original_id != ''""",
                (rgn,),
            ) as cur:
                products = await cur.fetchall()

            total = len(products)
            yield f"📦 [{rgn}] {total} игр без эдишенов"
            if not total:
                continue

            ps       = await get_price_settings(conn)
            updated  = 0
            errors   = 0
            sem      = asyncio.Semaphore(CONCURRENCY)

            async with ParserCls() as parser:

                async def process_one(prod: aiosqlite.Row) -> str | None:
                    """Fetch & save editions for one product. Returns log line or None."""
                    prod_id = prod["id"]
                    title   = prod["title"]
                    orig_id = prod["original_id"]
                    url     = f"{base_url}/product/{orig_id}"

                    async with sem:
                        try:
                            editions = await parser.parse_editions(url, rgn)
                        except Exception as e:
                            log.warning("parse_editions %s [%s]: %s", orig_id, rgn, e)
                            return None  # skip, not an error worth counting
                        finally:
                            await asyncio.sleep(REQUEST_DELAY)

                    if len(editions) < 2:
                        return None  # single-edition product — nothing to do

                    # Save to DB
                    try:
                        await conn.execute(
                            "DELETE FROM game_editions WHERE parent_product_id=? AND region=?",
                            (prod_id, rgn),
                        )
                        for ed in editions:
                            currency  = ed.get("currency", "UAH")
                            raw_price = float(ed.get("price") or 0)
                            raw_old   = ed.get("old_price")

                            if currency == "TRY":
                                p_uah, o_uah = None, None
                                p_try = raw_price
                                o_try = float(raw_old) if raw_old is not None else None
                            else:
                                p_uah = raw_price
                                o_uah = float(raw_old) if raw_old is not None else None
                                p_try, o_try = None, None

                            byn = calc_price_byn(
                                {
                                    "price_uah":    p_uah or 0,
                                    "price_try":    p_try or 0,
                                    "product_type": "game",
                                    "price_byn":    None,
                                    "price_byn_tr": None,
                                },
                                ps,
                            )
                            await conn.execute(
                                """INSERT INTO game_editions
                                     (parent_product_id, edition_name,
                                      price_uah, price_try, price_byn, price_byn_tr,
                                      old_price_uah, old_price_try,
                                      discount_pct, platform, ps_store_url,
                                      region, is_free, is_active)
                                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                                (
                                    prod_id,
                                    ed.get("edition_name", ""),
                                    p_uah, p_try,
                                    byn.get("price_byn"), byn.get("price_byn_tr"),
                                    o_uah, o_try,
                                    ed.get("discount_pct", 0),
                                    ed.get("platform", "PS4/PS5"),
                                    ed.get("ps_store_url", ""),
                                    rgn,
                                    1 if ed.get("is_free") else 0,
                                ),
                            )
                        await conn.execute(
                            "UPDATE products SET has_editions=1 WHERE id=?", (prod_id,)
                        )
                        await conn.commit()
                        return f"✅ {title[:45]} — {len(editions)} эдишенов"
                    except Exception as e:
                        log.error("save editions %s: %s", title, e)
                        return f"❌ {title[:35]}: {e}"

                # Process in batches of CONCURRENCY for progress feedback
                BATCH = CONCURRENCY * 4  # 20 products per yield
                for batch_start in range(0, total, BATCH):
                    batch    = products[batch_start: batch_start + BATCH]
                    results  = await asyncio.gather(
                        *[process_one(p) for p in batch],
                        return_exceptions=True,
                    )
                    for r in results:
                        if isinstance(r, Exception):
                            errors += 1
                        elif isinstance(r, str):
                            if r.startswith("✅"):
                                updated += 1
                            else:
                                errors += 1
                            yield r

                    done = min(batch_start + BATCH, total)
                    yield f"   [{rgn}] {done}/{total} обработано — эдишенов: {updated}, ошибок: {errors}"

            grand_updated += updated
            grand_errors  += errors
            yield f"✅ [{rgn}] Готово: {updated} игр с эдишенами, {errors} ошибок"

    except Exception as e:
        yield f"❌ Критическая ошибка: {e}"
        log.exception("fetch_editions_task failed")
    finally:
        await conn.close()

    yield f"🏁 Итого: {grand_updated} товаров с эдишенами обновлено"

"""
Task: fetch PS Store deals and apply discounts to the catalogue.

Match priority:
  1. original_id  → UPDATE discount_pct + price_uah on matched rows
  2. title        → UPDATE discount_pct + price_uah on matched rows (case-insensitive)
  3. not found    → INSERT via save_product (new discounted item)

Only records with discount_pct > 0 are processed.
"""
from __future__ import annotations
from typing import AsyncIterator

from parser.db import get_connection, ensure_categories, log_start, log_finish
from parser.parsers.ua_parser import UaParser
from parser.config import DEALS_CATEGORY_ID


async def run() -> AsyncIterator[str]:
    yield "⏳ Парсинг скидок (UA)..."
    conn = await get_connection()
    log_id = await log_start(conn, "UA", "parse_sales")
    added = updated = errors = 0

    try:
        cat_map = await ensure_categories(conn)
        ps_games_id = cat_map.get("ps-games", 1)

        async with UaParser() as parser:
            yield f"📥 Загрузка раздела скидок (ID: {DEALS_CATEGORY_ID[:8]}...)..."
            raws = await parser.fetch_all(DEALS_CATEGORY_ID, max_pages=30)
            yield f"   Получено {len(raws)} записей"

            by_id = by_title = inserted = 0

            for raw in raws:
                parsed = parser.parse_product(raw, "PS5/PS4")
                if not parsed or parsed["discount_pct"] <= 0:
                    continue

                try:
                    matched = False

                    # 1) Match by original_id — only update price + discount
                    if parsed["original_id"]:
                        cur = await conn.execute(
                            """UPDATE products
                               SET discount_pct=?, price_uah=?, updated_at=CURRENT_TIMESTAMP
                               WHERE original_id=?""",
                            (parsed["discount_pct"], parsed["price_uah"], parsed["original_id"]),
                        )
                        if cur.rowcount > 0:
                            by_id += 1
                            updated += cur.rowcount
                            matched = True

                    # 2) Match by title (case-insensitive)
                    if not matched and parsed["title"]:
                        cur = await conn.execute(
                            """UPDATE products
                               SET discount_pct=?, price_uah=?, updated_at=CURRENT_TIMESTAMP
                               WHERE LOWER(title)=LOWER(?)""",
                            (parsed["discount_pct"], parsed["price_uah"], parsed["title"]),
                        )
                        if cur.rowcount > 0:
                            by_title += 1
                            updated += cur.rowcount
                            matched = True

                    # 3) Not found — insert as new product
                    if not matched:
                        parsed["category_id"] = ps_games_id
                        await parser.save_product(parsed, [], conn=conn)
                        inserted += 1
                        added += 1

                except Exception as e:
                    errors += 1

            await conn.commit()
            yield (
                f"   По ID: {by_id}, по названию: {by_title}, "
                f"новых: {inserted}, ошибок: {errors}"
            )

        yield f"✅ Готово — обновлено: {updated}, добавлено: {added}, ошибок: {errors}"
        await log_finish(conn, log_id, status="done", added=added, updated=updated, errors=errors)

    except Exception as e:
        yield f"❌ Критическая ошибка: {e}"
        await log_finish(conn, log_id, status="error", errors=errors, details=str(e))
    finally:
        await conn.close()

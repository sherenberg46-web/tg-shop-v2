"""Task: parse preorders from PS Store and upsert them."""
from __future__ import annotations
from typing import AsyncIterator

from parser.db import get_connection, ensure_categories, log_start, log_finish
from parser.parsers.ua_parser import UaParser
from parser.config import PREORDERS_CATEGORY_ID


async def run() -> AsyncIterator[str]:
    yield "⏳ Парсинг предзаказов (UA)..."
    conn = await get_connection()
    log_id = await log_start(conn, "UA", "parse_preorders")
    saved = errors = 0

    try:
        cat_map = await ensure_categories(conn)
        ps_games_id = cat_map.get("ps-games", 1)

        async with UaParser() as parser:
            yield f"📥 Загрузка предзаказов (ID: {PREORDERS_CATEGORY_ID[:8]}...)..."
            raws = await parser.fetch_all(PREORDERS_CATEGORY_ID, max_pages=30)
            yield f"   Получено {len(raws)} записей"

            for raw in raws:
                parsed = parser.parse_product(raw, "PS5/PS4")
                if not parsed:
                    errors += 1
                    continue

                parsed["category_id"] = ps_games_id
                parsed["is_preorder"] = 1

                try:
                    await parser.save_product(parsed, [], conn=conn)
                    saved += 1
                except Exception as e:
                    errors += 1

            await conn.commit()

        yield f"✅ Готово — сохранено: {saved}, ошибок: {errors}"
        await log_finish(conn, log_id, status="done", added=saved, errors=errors)

    except Exception as e:
        yield f"❌ Критическая ошибка: {e}"
        await log_finish(conn, log_id, status="error", errors=errors, details=str(e))
    finally:
        await conn.close()

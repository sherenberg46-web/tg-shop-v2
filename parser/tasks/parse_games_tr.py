"""
Task: parse ALL PS5 + PS4 games from the Turkish PS Store.

Mirror of parse_games.py but for TR region using TrParser.
Editions extracted from skus inline; batarangs editions handled by fetch_editions_task.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator

from parser.db import get_connection, ensure_categories, log_start, log_finish
from parser.parsers.tr_parser import TrParser
from parser.config import PS_CATEGORIES

log = logging.getLogger(__name__)

_BASE_URL = "https://store.playstation.com/tr-tr"

MAX_PAGES = 400


async def run() -> AsyncIterator[str]:
    yield "⏳ Парсинг игр (TR)..."
    conn = await get_connection()
    log_id = await log_start(conn, "TR", "parse_games")
    saved = errors = 0

    try:
        cat_map = await ensure_categories(conn)
        ps_games_id = cat_map.get("ps-games", 1)

        async with TrParser() as parser:
            for pk, category_id in PS_CATEGORIES.items():
                platform = "PS5" if "ps5" in pk else "PS4"
                yield f"📥 Загрузка {platform} TR..."

                try:
                    raws = await parser.fetch_all(category_id, max_pages=MAX_PAGES)
                    yield f"   Получено {len(raws)} записей из PS Store TR"

                    batch_saved = batch_errors = 0
                    for i, raw in enumerate(raws):
                        parsed = parser.parse_product(raw, platform)
                        if not parsed:
                            batch_errors += 1
                            continue

                        parsed["category_id"] = ps_games_id

                        product_url = f"{_BASE_URL}/product/{parsed.get('original_id', '')}"
                        editions = parser._editions_from_raw(raw, product_url)

                        try:
                            await parser.save_product(parsed, editions, conn=conn)
                            batch_saved += 1
                        except Exception as e:
                            log.error("save_product error: %s", e)
                            batch_errors += 1

                        if (i + 1) % 500 == 0:
                            await conn.commit()
                            yield f"   {platform}: {i + 1}/{len(raws)} обработано..."

                    await conn.commit()
                    saved += batch_saved
                    errors += batch_errors
                    yield f"   ✅ {platform}: сохранено {batch_saved}, ошибок {batch_errors}"

                except Exception as e:
                    yield f"   ❌ Ошибка {platform}: {e}"
                    log.exception("parse_games TR %s failed", pk)
                    errors += 1

        yield f"✅ TR Готово — сохранено: {saved}, ошибок: {errors}"
        await log_finish(conn, log_id, status="done", added=saved, errors=errors)

    except Exception as e:
        yield f"❌ Критическая ошибка: {e}"
        await log_finish(conn, log_id, status="error", errors=errors, details=str(e))
    finally:
        await conn.close()

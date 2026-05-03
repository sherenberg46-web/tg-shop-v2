"""
Task: reset all discounts to 0.

Uses BaseParser.reset_sales() which clears discount_pct / old_price
on both products and game_editions for the given region.
Runs for all configured regions (UA, TR).
"""
from __future__ import annotations
from typing import AsyncIterator

from parser.db import get_connection, log_start, log_finish
from parser.parsers.ua_parser import UaParser
from parser.parsers.tr_parser import TrParser


async def run() -> AsyncIterator[str]:
    yield "⏳ Сброс скидок..."
    conn = await get_connection()
    log_id = await log_start(conn, "ALL", "reset_sales")

    try:
        # Count before
        async with conn.execute(
            "SELECT COUNT(*) FROM products WHERE discount_pct > 0"
        ) as cur:
            row = await cur.fetchone()
        count = row[0] if row else 0
        yield f"📊 Товаров со скидкой до сброса: {count}"

        # Reset per region using BaseParser.reset_sales()
        async with UaParser() as parser_ua:
            await parser_ua.reset_sales()
            yield "   ✅ UA — скидки сброшены"

        async with TrParser() as parser_tr:
            await parser_tr.reset_sales()
            yield "   ✅ TR — скидки сброшены"

        yield f"✅ Готово — сброшено скидок у {count} товаров"
        await log_finish(conn, log_id, status="done", updated=count)

    except Exception as e:
        yield f"❌ Ошибка: {e}"
        await log_finish(conn, log_id, status="error", details=str(e))
    finally:
        await conn.close()

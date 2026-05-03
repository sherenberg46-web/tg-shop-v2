"""
Ukrainian PS Store parser.

CATEGORIES stores full PS Store web URLs — UUID is extracted automatically.
fetch_all() (inherited from BaseParser) already fetches ALL pages via GraphQL
using offset-based pagination, so no additional page looping is needed here.
"""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator

from parser.base_parser import BaseParser, parse_price_string, detect_currency
from parser.db import get_connection, ensure_categories, log_start, log_finish

log = logging.getLogger(__name__)

# Extracts UUID from a PS Store URL like /category/{uuid}/1
_UUID_RE = re.compile(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})', re.I)


def _cat_uuid(url_or_id: str) -> str:
    """Return the UUID portion of a PS Store category URL (or the string itself if already a UUID)."""
    m = _UUID_RE.search(url_or_id)
    return m.group(1).lower() if m else url_or_id


class UAParser(BaseParser):
    BASE_URL = "https://store.playstation.com/ru-ua"
    country  = "UA"
    region   = "UA"
    CURRENCY = "UAH"

    # Full PS Store web URLs — UUID is extracted at runtime.
    # hot_deals removed (category no longer active on PS Store).
    CATEGORIES: dict[str, str] = {
        "sales":     "https://store.playstation.com/ru-ua/category/3f772501-f6f8-49b7-abac-874a88ca4897/1",
        "new_games": "https://store.playstation.com/ru-ua/category/e1699f77-77e1-43ca-a296-26d08abacb0f/1",
        "preorders": "https://store.playstation.com/ru-ua/category/3bf499d7-7acf-4931-97dd-2667494ee2c9/1",
    }

    async def parse_category(
        self, category_key: str, task_type: str
    ) -> AsyncIterator[str]:
        """
        Async generator — yields log strings for SSE streaming.

        Steps:
          1. Create parser_log entry
          2. reset_sales() if task_type == 'sales'
          3. Fetch all products via GraphQL (all pages, offset-based)
          4. For each product: extract editions from skus, save_product()
          5. Finalise parser_log
        """
        conn = await get_connection()
        log_id = await log_start(conn, self.region, task_type)
        saved = errors = 0

        try:
            if task_type == "sales":
                await self.reset_sales()
                yield "🔄 Скидки сброшены для UA"

            url = self.CATEGORIES.get(category_key)
            if not url:
                msg = f"Неизвестная категория: {category_key}"
                yield f"❌ {msg}"
                await log_finish(conn, log_id, status="error", details=msg)
                return

            category_id = _cat_uuid(url)
            cat_map = await ensure_categories(conn)
            ps_games_id = cat_map.get("ps-games", 1)

            yield f"📥 Загрузка [{category_key}] UA (ID: {category_id[:8]}...)..."
            # fetch_all() paginates automatically via GraphQL offset
            raws = await self.fetch_all(category_id, max_pages=50)
            yield f"   Получено {len(raws)} записей из PS Store UA"

            for raw in raws:
                parsed = self.parse_product(
                    raw, None,
                    allow_no_price=(task_type == "preorders"),
                )
                if not parsed:
                    errors += 1
                    continue

                parsed["category_id"] = ps_games_id
                parsed["task_type"]   = task_type
                if task_type == "preorders":
                    parsed["is_preorder"] = 1

                product_url = f"{self.BASE_URL}/product/{parsed['original_id']}"
                editions = self._editions_from_raw(raw, product_url)

                try:
                    await self.save_product(parsed, editions, conn=conn)
                    saved += 1
                except Exception as e:
                    log.error("save_product error: %s", e)
                    errors += 1

            await conn.commit()
            yield f"✅ [{category_key}] UA — сохранено: {saved}, ошибок: {errors}"
            await log_finish(conn, log_id, status="done", added=saved, errors=errors)

            # Auto-push to Railway
            from parser.scripts.push_to_railway import push_region
            async for line in push_region("UA"):
                yield line

        except Exception as e:
            yield f"❌ Критическая ошибка: {e}"
            await log_finish(conn, log_id, status="error", details=str(e))
        finally:
            await conn.close()

    def _editions_from_raw(self, raw: dict, product_url: str) -> list[dict]:
        """Extract editions from GraphQL skus. Returns [] if ≤1 sku."""
        skus = raw.get("skus") or []
        if len(skus) <= 1:
            return []
        return self._parse_sku_list(skus, product_url, self.region)

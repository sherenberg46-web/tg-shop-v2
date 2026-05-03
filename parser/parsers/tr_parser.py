"""
Turkish PS Store parser.

Like UAParser but country=TR, currency=TRY.
parse_product() is overridden to extract TRY prices → price_try column.
"""
from __future__ import annotations

import logging
import re
from typing import AsyncIterator

from parser.base_parser import BaseParser, parse_price_string, detect_currency, normalize_platform, parse_release_date
from parser.db import get_connection, ensure_categories, log_start, log_finish

log = logging.getLogger(__name__)

_UUID_RE = re.compile(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})', re.I)


def _cat_uuid(url_or_id: str) -> str:
    m = _UUID_RE.search(url_or_id)
    return m.group(1).lower() if m else url_or_id


class TrParser(BaseParser):
    BASE_URL = "https://store.playstation.com/tr-tr"
    country  = "TR"
    region   = "TR"
    CURRENCY = "TRY"

    CATEGORIES: dict[str, str] = {
        "sales":     "https://store.playstation.com/en-tr/category/3f772501-f6f8-49b7-abac-874a88ca4897/1",
        "new_games": "https://store.playstation.com/en-tr/category/e1699f77-77e1-43ca-a296-26d08abacb0f/1",
        "preorders": "https://store.playstation.com/en-tr/category/3bf499d7-7acf-4931-97dd-2667494ee2c9/1",
    }

    # ── Price extraction (TRY) ────────────────────────────────────────────────

    def parse_product(
        self, raw: dict, platform: str, allow_no_price: bool = False
    ) -> dict | None:
        """
        Extract TRY price into price_try; price_uah = 0.
        Pass allow_no_price=True for preorders whose price is not yet set.
        """
        try:
            name = raw.get("name", "")
            if not name:
                return None

            price_try    = 0.0
            discount_pct = 0

            for cta in raw.get("webctas") or []:
                pi = cta.get("price") or {}
                base_str = pi.get("basePrice", "")
                disc_str = pi.get("discountedPrice", "")
                if detect_currency(base_str or disc_str) != "TRY":
                    continue
                bv = parse_price_string(base_str)
                dv = parse_price_string(disc_str)
                if dv > 0:
                    price_try = dv
                    if bv > dv:
                        discount_pct = round((1 - dv / bv) * 100)
                elif bv > 0:
                    price_try = bv
                if price_try > 0:
                    break

            if price_try <= 0:
                price_obj = raw.get("price") or {}
                if isinstance(price_obj, dict):
                    base_str = price_obj.get("basePrice", "")
                    disc_str = price_obj.get("discountedPrice", "")
                    if detect_currency(base_str or disc_str) == "TRY":
                        bv = parse_price_string(base_str)
                        dv = parse_price_string(disc_str)
                        if dv > 0:
                            price_try = dv
                            if bv > dv:
                                discount_pct = round((1 - dv / bv) * 100)
                        elif bv > 0:
                            price_try = bv

            if price_try <= 0:
                skus = raw.get("skus") or []
                if skus:
                    pi = skus[0].get("price") or {}
                    if detect_currency(pi.get("basePrice", "")) == "TRY":
                        pv = pi.get("basePriceValue", 0)
                        if pv:
                            price_try = float(pv)

            if price_try <= 0 and not allow_no_price:
                return None

            image_url = ""
            for m in raw.get("media") or []:
                if m.get("role") in ("MASTER", "GAMEHUB_COVER_ART", "PORTRAIT_BANNER"):
                    image_url = m.get("url", "")
                    break
            if not image_url and raw.get("media"):
                image_url = raw["media"][0].get("url", "")

            original_id = raw.get("id", "") or ""
            concept = raw.get("concept") or {}
            if not original_id:
                original_id = str(concept.get("id", ""))

            si = raw.get("storeInfo") or {}
            release_date = parse_release_date(
                si.get("releaseDate") or concept.get("releaseDate")
            )

            platforms = raw.get("platforms") or []
            platform = normalize_platform(platforms) if platforms else None

            desc = raw.get("description", "") or ""
            if len(desc) > 500:
                desc = desc[:497] + "..."

            genres = (
                raw.get("localizedGenreNames")
                or concept.get("localizedGenreNames")
                or []
            )
            genre = ", ".join(str(g) for g in genres[:2]) if genres else ""

            requires_ps_plus = bool(
                raw.get("requiresSubscription")
                or raw.get("requiresPSPlus")
                or raw.get("psPlus")
                or (raw.get("plus") or {}).get("required")
                or any(
                    (s or {}).get("required") or (s or {}).get("isRequired")
                    for s in (raw.get("subscriptions") or [])
                )
            )

            discount_until: str | None = None
            for cta in raw.get("webctas") or []:
                pi = cta.get("price") or {}
                end = (
                    pi.get("promotionEndDate")
                    or pi.get("discountEndDate")
                    or pi.get("endDate")
                )
                if end:
                    discount_until = str(end)[:10]
                    break

            return {
                "title":             name,
                "description":       desc,
                "image_url":         image_url,
                "price_uah":         0,
                "price_try":         price_try,
                "platform":          platform,
                "rating":            0,
                "is_featured":       0,
                "discount_pct":      discount_pct,
                "original_id":       original_id,
                "release_date":      release_date,
                "product_type":      "game",
                "is_preorder":       0,
                "region":            self.region,
                "genre":             genre,
                "requires_ps_plus":  int(requires_ps_plus),
                "discount_until":    discount_until,
            }
        except Exception as e:
            log.error("TrParser.parse_product error: %s", e)
            return None

    # ── Category parsing ──────────────────────────────────────────────────────

    async def parse_category(
        self, category_key: str, task_type: str
    ) -> AsyncIterator[str]:
        conn = await get_connection()
        log_id = await log_start(conn, self.region, task_type)
        saved = errors = 0

        try:
            if task_type == "sales":
                await self.reset_sales()
                yield "🔄 Скидки сброшены для TR"

            url = self.CATEGORIES.get(category_key)
            if not url:
                msg = f"Неизвестная категория: {category_key}"
                yield f"❌ {msg}"
                await log_finish(conn, log_id, status="error", details=msg)
                return

            category_id = _cat_uuid(url)
            cat_map = await ensure_categories(conn)
            ps_games_id = cat_map.get("ps-games", 1)

            yield f"📥 Загрузка [{category_key}] TR (ID: {category_id[:8]}...)..."
            raws = await self.fetch_all(category_id, max_pages=50)
            yield f"   Получено {len(raws)} записей из PS Store TR"

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
            yield f"✅ [{category_key}] TR — сохранено: {saved}, ошибок: {errors}"
            await log_finish(conn, log_id, status="done", added=saved, errors=errors)

            # Auto-push to Railway
            from parser.scripts.push_to_railway import push_region
            async for line in push_region("TR"):
                yield line

        except Exception as e:
            yield f"❌ Критическая ошибка: {e}"
            await log_finish(conn, log_id, status="error", details=str(e))
        finally:
            await conn.close()

    def _editions_from_raw(self, raw: dict, product_url: str) -> list[dict]:
        skus = raw.get("skus") or []
        if len(skus) <= 1:
            return []
        return self._parse_sku_list(skus, product_url, self.region)

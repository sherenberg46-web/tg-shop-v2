"""
Push locally parsed products to Railway backend via import API.

Usage:
    python -m parser.scripts.push_to_railway [--region UA|TR|ALL] [--dry-run]

Environment variables (or set in .env):
    RAILWAY_API_URL   — e.g. https://tg-shop-production-1b03.up.railway.app/api/v1
    ADMIN_PASSWORD    — admin panel password (same as backend ADMIN_PASSWORD)

The script reads all active products from the local DB and posts them
to POST /api/v1/admin/import-products in batches of 100.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

import aiosqlite
import httpx
from dotenv import load_dotenv

# Load .env files
_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / "parser" / ".env", override=True)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RAILWAY_API_URL = os.environ.get(
    "RAILWAY_API_URL",
    "https://tg-shop-production-1b03.up.railway.app/api/v1",
).rstrip("/")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")
DB_PATH = Path(os.environ.get("DB_PATH", "database/shop.db"))
if not DB_PATH.is_absolute():
    DB_PATH = _root / DB_PATH

BATCH_SIZE = 100


def _token() -> str:
    return hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()


async def load_products(region: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT title, description, image_url,
                   price_uah, price_try, price_byn, price_byn_tr,
                   platform, discount_pct, discount_until,
                   original_id, release_date, product_type,
                   is_preorder, is_featured, rating,
                   region, task_type, genre, requires_ps_plus
            FROM products
            WHERE is_active = 1
        """
        params: list = []
        if region != "ALL":
            sql += " AND region = ?"
            params.append(region.upper())
        sql += " ORDER BY id"
        rows = await db.execute_fetchall(sql, params)
        return [dict(r) for r in rows]


async def push_products(products: list[dict], dry_run: bool = False):
    """
    Async generator: push product list to Railway, yield log lines.
    Yields strings suitable for SSE streaming or CLI output.
    """
    if not products:
        yield "⚠️ Нет продуктов для отправки"
        return

    if not RAILWAY_API_URL:
        yield "⚠️ RAILWAY_API_URL не задан — пропускаем синхронизацию"
        return

    yield f"🚀 Отправка {len(products)} продуктов на Railway..."

    headers = {
        "Content-Type": "application/json",
        "X-Admin-Token": _token(),
    }

    total_inserted = total_updated = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(products), BATCH_SIZE):
            batch = products[i: i + BATCH_SIZE]
            if dry_run:
                yield f"[DRY RUN] Batch {i}–{i + len(batch)}: пропущено"
                continue

            payload = {"products": batch}
            try:
                resp = await client.post(
                    f"{RAILWAY_API_URL}/admin/import-products",
                    headers=headers,
                    content=json.dumps(payload, default=str),
                )
                if resp.status_code != 200:
                    yield f"❌ Batch {i}: {resp.status_code} — {resp.text[:200]}"
                    continue
                result = resp.json()
                total_inserted += result.get("inserted", 0)
                total_updated  += result.get("updated", 0)
            except Exception as e:
                yield f"❌ Batch {i}: {e}"

    yield f"✅ Railway sync: +{total_inserted} новых, ~{total_updated} обновлено"


async def push_region(region: str, dry_run: bool = False):
    """Async generator: load products for region from local DB, push to Railway."""
    products = await load_products(region)
    async for line in push_products(products, dry_run=dry_run):
        yield line


# ── Editions push ─────────────────────────────────────────────────────────────

async def load_editions(region: str) -> list[dict]:
    """Load game_editions with their product's original_id for pushing to Railway."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT ge.edition_name, ge.price_uah, ge.price_try, ge.price_byn, ge.price_byn_tr,
                   ge.old_price_uah, ge.old_price_try, ge.discount_pct,
                   ge.platform, ge.ps_store_url, ge.region, ge.is_free,
                   p.original_id AS product_original_id
            FROM game_editions ge
            JOIN products p ON p.id = ge.parent_product_id
            WHERE ge.region = ? AND ge.is_active = 1
              AND p.original_id IS NOT NULL AND p.original_id != ''
        """
        rows = await db.execute_fetchall(sql, (region.upper(),))
        return [dict(r) for r in rows]


async def push_editions(editions: list[dict], dry_run: bool = False):
    """Async generator: push editions to Railway in batches."""
    if not editions:
        yield "⚠️ Нет эдишенов для отправки"
        return

    if not RAILWAY_API_URL:
        yield "⚠️ RAILWAY_API_URL не задан"
        return

    yield f"🚀 Отправка {len(editions)} эдишенов на Railway..."
    headers = {"Content-Type": "application/json", "X-Admin-Token": _token()}
    inserted = updated = skipped = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(editions), BATCH_SIZE):
            batch = editions[i: i + BATCH_SIZE]
            if dry_run:
                yield f"[DRY RUN] Batch {i}–{i + len(batch)}: пропущено"
                continue
            try:
                resp = await client.post(
                    f"{RAILWAY_API_URL}/admin/import-editions",
                    headers=headers,
                    content=json.dumps({"editions": batch}, default=str),
                )
                if resp.status_code != 200:
                    yield f"❌ Batch {i}: {resp.status_code} — {resp.text[:200]}"
                    continue
                result = resp.json()
                inserted += result.get("inserted", 0)
                updated  += result.get("updated", 0)
                skipped  += result.get("skipped", 0)
            except Exception as e:
                yield f"❌ Batch {i}: {e}"

    yield f"✅ Editions sync: +{inserted} новых, ~{updated} обновлено, {skipped} пропущено (нет продукта)"


async def push(products: list[dict], dry_run: bool) -> None:
    """CLI helper — wraps push_products and logs to stdout."""
    async for line in push_products(products, dry_run=dry_run):
        log.info(line)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Push local products/editions to Railway")
    parser.add_argument("--region", default="ALL", choices=["UA", "TR", "ALL"])
    parser.add_argument("--editions", action="store_true", help="Push editions instead of products")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.editions:
        regions = ["UA", "TR"] if args.region == "ALL" else [args.region]
        for rgn in regions:
            eds = await load_editions(rgn)
            log.info("Loaded %d editions from local DB (region=%s)", len(eds), rgn)
            async for line in push_editions(eds, dry_run=args.dry_run):
                log.info(line)
    else:
        products = await load_products(args.region)
        log.info("Loaded %d products from local DB (region=%s)", len(products), args.region)
        await push(products, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())

"""
Recalculate price_byn / price_byn_tr for ALL products in the local DB,
then push everything to Railway.

Usage:
    python -m parser.scripts.recalc_prices [--dry-run] [--no-push]

Options:
    --dry-run   Print what would change but don't write to DB or Railway
    --no-push   Recalc local DB only, skip Railway push
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import aiosqlite

_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env")
load_dotenv(_root / "parser" / ".env", override=True)

from parser.config import get_price_settings, calc_price_byn, uah_to_byn, try_to_byn, clamp_byn

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DB_PATH = Path(os.environ.get("DB_PATH", "database/shop.db"))
if not DB_PATH.is_absolute():
    DB_PATH = _root / DB_PATH


async def recalc(dry_run: bool = False, force: bool = False) -> dict:
    """
    Recalculate price_byn / price_byn_tr for every product.

    Rules:
    - Manually overridden prices (originally set via admin panel) are preserved
      if they differ from the formula result by more than 10% — we don't blindly
      overwrite admin overrides.
    - NULL / 0 prices are always recomputed from formula.
    - subscription / topup: price_byn = price_uah (direct 1:1, no markup)
    """
    stats = {"updated": 0, "skipped_no_src": 0, "manual_kept": 0, "errors": 0}

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        ps = await get_price_settings(db)
        log.info("Rates: UAH=%.4f, TRY=%.4f", ps.uah_rate, ps.try_rate)
        log.info("UAH markups: %s", ps.uah_markups)
        log.info("TRY markups: %s", ps.try_markups)

        rows = await db.execute_fetchall(
            "SELECT id, price_uah, price_try, price_byn, price_byn_tr, product_type FROM products"
        )
        log.info("Loaded %d products", len(rows))

        for row in rows:
            prod_id      = row["id"]
            price_uah    = row["price_uah"] or 0.0
            price_try    = row["price_try"] or 0.0
            cur_byn      = row["price_byn"]
            cur_byn_tr   = row["price_byn_tr"]
            product_type = row["product_type"] or "game"

            # Compute fresh values
            product_stub = {
                "price_uah":    price_uah,
                "price_try":    price_try,
                "product_type": product_type,
                "price_byn":    None,    # force recalc
                "price_byn_tr": None,
            }
            computed = calc_price_byn(product_stub, ps)
            new_byn    = computed.get("price_byn")
            new_byn_tr = computed.get("price_byn_tr")

            # If both source prices are 0 — nothing to compute
            if not price_uah and not price_try:
                if not cur_byn and not cur_byn_tr:
                    stats["skipped_no_src"] += 1
                continue

            if new_byn is None and new_byn_tr is None:
                stats["skipped_no_src"] += 1
                continue

            # Detect manual overrides: current value set but differs >10% from formula
            def _is_manual(cur, computed_val) -> bool:
                if cur is None or cur == 0:
                    return False           # NULL/0 → always overwrite
                if computed_val is None:
                    return True            # formula gives nothing → keep manual
                if computed_val == 0:
                    return True
                diff = abs(cur - computed_val) / max(computed_val, 1)
                return diff > 0.10         # >10% deviation → treat as manual

            final_byn    = new_byn    if force else (cur_byn    if _is_manual(cur_byn,    new_byn)    else new_byn)
            final_byn_tr = new_byn_tr if force else (cur_byn_tr if _is_manual(cur_byn_tr, new_byn_tr) else new_byn_tr)

            if final_byn == cur_byn and final_byn_tr == cur_byn_tr:
                continue  # nothing changed

            if not dry_run:
                await db.execute(
                    "UPDATE products SET price_byn=?, price_byn_tr=? WHERE id=?",
                    (final_byn, final_byn_tr, prod_id),
                )
            stats["updated"] += 1

        if not dry_run:
            await db.commit()

        # Summary after recalc
        if not dry_run:
            row = await db.execute_fetchall(
                "SELECT COUNT(*) FROM products WHERE price_byn IS NULL OR price_byn=0"
            )
            still_zero_byn = row[0][0]
            row2 = await db.execute_fetchall(
                "SELECT COUNT(*) FROM products WHERE price_byn_tr IS NULL OR price_byn_tr=0"
            )
            still_zero_tr = row2[0][0]
            log.info("After recalc — null/0 price_byn: %d  |  null/0 price_byn_tr: %d",
                     still_zero_byn, still_zero_tr)

    return stats


async def main() -> None:
    parser = argparse.ArgumentParser(description="Recalculate BYN prices and optionally push to Railway")
    parser.add_argument("--dry-run", action="store_true", help="Don't write anything")
    parser.add_argument("--no-push", action="store_true", help="Skip Railway push")
    parser.add_argument("--force", action="store_true", help="Overwrite even manual-looking prices")
    args = parser.parse_args()

    log.info("=== Recalculating prices (dry_run=%s, force=%s) ===", args.dry_run, args.force)
    stats = await recalc(dry_run=args.dry_run, force=args.force)
    log.info("Result: updated=%d  skipped_no_price=%d  errors=%d",
             stats["updated"], stats["skipped_no_src"], stats["errors"])

    if args.dry_run:
        log.info("Dry run — no changes written.")
        return

    if args.no_push:
        log.info("--no-push: skipping Railway sync.")
        return

    log.info("=== Pushing to Railway ===")
    from parser.scripts.push_to_railway import push_region
    for region in ("UA", "TR"):
        log.info("--- %s ---", region)
        async for line in push_region(region):
            log.info(line)


if __name__ == "__main__":
    asyncio.run(main())

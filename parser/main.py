"""
Parser web interface — standalone FastAPI application.

Run from project root:
    uvicorn parser.main:app --reload --port 8001

Endpoints:
    GET  /                         — index.html (Basic auth)
    GET  /products                 — products.html (Basic auth)
    GET  /api/status               — DB stats per region
    POST /api/run/{region}/{task}  — start a parse task (SSE stream)
    GET  /api/logs                 — last N runs from parser_log
    GET  /api/products             — list products with filters
    DELETE /api/products/{id}      — delete a product
    PATCH  /api/products/{id}/price — update price_byn / price_byn_tr
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from parser.config import ADMIN_PASSWORD
from parser.db import get_connection

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="PS Store Parser", docs_url=None, redoc_url=None)
security = HTTPBasic()

TEMPLATE_PATH          = Path(__file__).parent / "templates" / "index.html"
PRODUCTS_TEMPLATE_PATH = Path(__file__).parent / "templates" / "products.html"

# ── Valid tasks per region ────────────────────────────────────────────────────
CATEGORY_TASKS = ("new_games", "sales", "preorders")
SPECIAL_TASKS  = ("all", "reset_sales")
ALL_TASKS      = CATEGORY_TASKS + SPECIAL_TASKS

# Task labels for the UI
TASK_LABELS: dict[str, str] = {
    "new_games":   "🆕 Новые игры",
    "sales":       "🔥 Скидки",
    "preorders":   "⏳ Предзаказы",
    "all":         "🔄 Обновить всё",
    "reset_sales": "🗑️ Сбросить скидки",
}

# Active task guard
_running_task: asyncio.Task | None = None


# ── Auth ──────────────────────────────────────────────────────────────────────

def _check_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    pw_hash = hashlib.sha256(credentials.password.encode()).hexdigest()
    expected = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    if credentials.username != "admin" or pw_hash != expected:
        raise HTTPException(
            status_code=401, detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(_: str = Depends(_check_auth)):
    if TEMPLATE_PATH.exists():
        return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Parser</h1><p>template not found</p>")


@app.get("/products", response_class=HTMLResponse)
async def products_page(_: str = Depends(_check_auth)):
    if PRODUCTS_TEMPLATE_PATH.exists():
        return HTMLResponse(PRODUCTS_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Products</h1><p>template not found</p>")


@app.get("/api/status")
async def get_status(_: str = Depends(_check_auth)):
    """DB stats per region + last runs."""
    conn = await get_connection()
    try:
        result: dict = {"running": bool(_running_task and not _running_task.done())}
        for region in ("UA", "TR"):
            async with conn.execute(
                "SELECT COUNT(*) FROM products WHERE is_active=1 AND region=?", (region,)
            ) as cur:
                total = (await cur.fetchone())[0]
            async with conn.execute(
                "SELECT COUNT(*) FROM products WHERE discount_pct>0 AND region=?", (region,)
            ) as cur:
                on_sale = (await cur.fetchone())[0]
            async with conn.execute(
                """SELECT started_at, finished_at, status, task_type
                   FROM parser_log WHERE region=?
                   ORDER BY id DESC LIMIT 1""",
                (region,),
            ) as cur:
                last = await cur.fetchone()
            result[region.lower()] = {
                "total":   total,
                "on_sale": on_sale,
                "last_run": dict(last) if last else None,
            }
        return result
    finally:
        await conn.close()


@app.get("/api/tasks")
async def list_tasks(_: str = Depends(_check_auth)):
    """List of available tasks for the UI."""
    return [
        {"id": f"{region}-{task}", "region": region, "task": task,
         "label": f"{TASK_LABELS.get(task, task)} {region}"}
        for region in ("UA", "TR")
        for task in ALL_TASKS
    ]


@app.post("/api/run/{region}/{task}")
async def run_task(
    region: str, task: str, _: str = Depends(_check_auth)
):
    """
    Start a parse task and stream log lines via SSE.

    region: ua | tr
    task:   new_games | sales | preorders | hot_deals | all | reset_sales
    """
    global _running_task

    region = region.upper()
    if region not in ("UA", "TR"):
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}")
    if task not in ALL_TASKS:
        raise HTTPException(status_code=400, detail=f"Unknown task: {task}")
    if _running_task and not _running_task.done():
        raise HTTPException(status_code=409, detail="Другая задача уже запущена")

    label = f"{TASK_LABELS.get(task, task)} {region}"

    async def event_generator() -> AsyncIterator[dict]:
        global _running_task

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def producer():
            try:
                async for line in _make_generator(region, task):
                    await queue.put(line)
            except Exception as e:
                await queue.put(f"❌ Необработанная ошибка: {e}")
            finally:
                await queue.put(None)  # sentinel

        _running_task = asyncio.create_task(producer())

        yield {"event": "start", "data": f"▶ {label}"}
        while True:
            line = await queue.get()
            if line is None:
                break
            yield {"event": "message", "data": line}
        yield {"event": "done", "data": "✅ Задача завершена"}

    return EventSourceResponse(event_generator())


@app.get("/api/logs")
async def get_logs(_: str = Depends(_check_auth), limit: int = 20):
    conn = await get_connection()
    try:
        async with conn.execute(
            """SELECT id, region, task_type, started_at, finished_at,
                      status, products_added, products_updated, errors_count, details
               FROM parser_log
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Products management API ───────────────────────────────────────────────────

@app.get("/api/products")
async def list_products(
    _: str = Depends(_check_auth),
    region:    Optional[str] = Query(None),
    type:      Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    search:    Optional[str] = Query(None),
    discount:  Optional[bool] = Query(None),
    page:      int = Query(1, ge=1),
    limit:     int = Query(50, ge=1, le=200),
):
    """List products with optional filters. Returns {items, total, page, pages}."""
    conn = await get_connection()
    try:
        conditions = []
        params: list = []

        if region:
            conditions.append("region = ?")
            params.append(region.upper())
        if type:
            conditions.append("product_type = ?")
            params.append(type)
        if task_type:
            conditions.append("task_type = ?")
            params.append(task_type)
        if search:
            conditions.append("title LIKE ?")
            params.append(f"%{search}%")
        if discount is True:
            conditions.append("discount_pct > 0")
        elif discount is False:
            conditions.append("discount_pct = 0")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        async with conn.execute(
            f"SELECT COUNT(*) FROM products {where}", params
        ) as cur:
            total = (await cur.fetchone())[0]

        offset = (page - 1) * limit
        async with conn.execute(
            f"""SELECT id, title, region, product_type, task_type, image_url,
                       price_uah, price_try, price_byn, price_byn_tr,
                       discount_pct, is_active, is_featured, original_id
                FROM products {where}
                ORDER BY id DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ) as cur:
            rows = await cur.fetchall()

        return {
            "items":  [dict(r) for r in rows],
            "total":  total,
            "page":   page,
            "pages":  max(1, -(-total // limit)),  # ceil division
        }
    finally:
        await conn.close()


@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, _: str = Depends(_check_auth)):
    conn = await get_connection()
    try:
        async with conn.execute("SELECT id FROM products WHERE id=?", (product_id,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Product not found")
        await conn.execute("DELETE FROM game_editions WHERE parent_product_id=?", (product_id,))
        await conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        await conn.commit()
        return {"ok": True}
    finally:
        await conn.close()


class PricePatch(BaseModel):
    price_byn:    Optional[int] = None
    price_byn_tr: Optional[int] = None


@app.patch("/api/products/{product_id}/price")
async def patch_price(product_id: int, body: PricePatch, _: str = Depends(_check_auth)):
    if body.price_byn is None and body.price_byn_tr is None:
        raise HTTPException(status_code=400, detail="Nothing to update")
    conn = await get_connection()
    try:
        async with conn.execute("SELECT id FROM products WHERE id=?", (product_id,)) as cur:
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Product not found")
        if body.price_byn is not None:
            await conn.execute(
                "UPDATE products SET price_byn=? WHERE id=?", (body.price_byn, product_id)
            )
        if body.price_byn_tr is not None:
            await conn.execute(
                "UPDATE products SET price_byn_tr=? WHERE id=?", (body.price_byn_tr, product_id)
            )
        await conn.commit()
        return {"ok": True}
    finally:
        await conn.close()


# ── Fetch Editions route ──────────────────────────────────────────────────────

@app.post("/api/run/editions/{region}")
async def run_fetch_editions(
    region: str, _: str = Depends(_check_auth)
):
    """
    Fetch game editions from PS Store product pages.
    region: ua | tr | all
    """
    global _running_task

    region = region.upper()
    if region not in ("UA", "TR", "ALL"):
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}")
    if _running_task and not _running_task.done():
        raise HTTPException(status_code=409, detail="Другая задача уже запущена")

    label = f"🎮 Загрузка эдишенов {region}"

    async def event_generator() -> AsyncIterator[dict]:
        global _running_task
        from parser.tasks.fetch_editions import fetch_editions_task

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def producer():
            try:
                async for line in fetch_editions_task(region):
                    await queue.put(line)
            except Exception as e:
                await queue.put(f"❌ Необработанная ошибка: {e}")
            finally:
                await queue.put(None)

        _running_task = asyncio.create_task(producer())
        yield {"event": "start", "data": f"▶ {label}"}
        while True:
            line = await queue.get()
            if line is None:
                break
            yield {"event": "message", "data": line}
        yield {"event": "done", "data": "✅ Задача завершена"}

    return EventSourceResponse(event_generator())


# ── Task dispatch ─────────────────────────────────────────────────────────────

async def _make_generator(region: str, task: str) -> AsyncIterator[str]:
    """Route region + task to the right parser method."""
    from parser.parsers.ua_parser import UAParser
    from parser.parsers.tr_parser import TrParser

    ParserCls = UAParser if region == "UA" else TrParser

    if task == "reset_sales":
        async with ParserCls() as parser:
            await parser.reset_sales()
            yield f"✅ Скидки сброшены для {region}"
        return

    if task == "all":
        # Run all categories sequentially; sales last (it resets discounts first)
        async with ParserCls() as parser:
            for cat in ("new_games", "preorders"):
                async for line in parser.parse_category(cat, cat):
                    yield line
            async for line in parser.parse_category("sales", "sales"):
                yield line
        return

    # Single category task
    async with ParserCls() as parser:
        async for line in parser.parse_category(task, task):
            yield line

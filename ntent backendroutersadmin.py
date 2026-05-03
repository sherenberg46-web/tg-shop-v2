from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite
from backend.database import get_db
from backend.schemas import ProductOut, EditionOut

router = APIRouter(prefix="/products", tags=["products"])

_SELECT = """
    SELECT id, category_id, title, description, image_url,
           price_uah, price_try, price_inr, price_pln,
           platform, rating, is_featured,
           discount_pct, discount_until,
           release_date, product_type, is_preorder
    FROM products
    WHERE is_active = 1
"""


async def _attach_editions(db: aiosqlite.Connection, products: list[dict]) -> list[dict]:
    """Attach editions list to each product."""
    if not products:
        return products
    ids = [p["id"] for p in products]
    placeholders = ",".join("?" * len(ids))
    rows = await db.execute_fetchall(
        f"""SELECT id, product_id, name, price_uah, price_try, price_inr, price_pln,
                   is_default, sort_order
            FROM product_editions
            WHERE product_id IN ({placeholders})
            ORDER BY sort_order""",
        ids,
    )
    editions_map: dict[int, list] = {}
    for r in rows:
        d = dict(r)
        editions_map.setdefault(d["product_id"], []).append(d)
    for p in products:
        p["editions"] = editions_map.get(p["id"], [])
    return products


@router.get("", response_model=list[ProductOut])
async def list_products(
    category_id: int | None = Query(None),
    featured: bool | None = Query(None),
    search: str | None = Query(None, min_length=2),
    section: str | None = Query(None),      # new|releases|preorder|top15|donate
    product_type: str | None = Query(None), # game|subscription
    sort: str | None = Query(None),         # discount|rating|release_date
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    sql, params = _SELECT, []

    # Filter out subscriptions by default in game sections
    if product_type:
        sql += " AND product_type = ?"
        params.append(product_type)

    if category_id is not None:
        sql += " AND category_id = ?"
        params.append(category_id)
    if featured is not None:
        sql += " AND is_featured = ?"
        params.append(int(featured))
    if search:
        sql += " AND title LIKE ?"
        params.append(f"%{search}%")

    # Section-specific filters
    today = date.today().isoformat()
    if section == "new":
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        sql += " AND product_type='game' AND is_preorder=0 AND release_date IS NOT NULL AND release_date >= ? AND release_date <= ?"
        params += [cutoff, today]
        sql += " ORDER BY release_date DESC"
    elif section == "releases":
        cutoff_near = (date.today() - timedelta(days=365)).isoformat()
        cutoff_far  = (date.today() - timedelta(days=90)).isoformat()
        sql += " AND product_type='game' AND is_preorder=0 AND release_date IS NOT NULL AND release_date >= ? AND release_date < ?"
        params += [cutoff_near, cutoff_far]
        sql += " ORDER BY release_date DESC"
    elif section == "preorder":
        sql += " AND product_type='game' AND release_date > ?"
        params.append(today)
        sql += " ORDER BY release_date ASC"
    elif section == "top15":
        sql += " AND product_type='game'"
        sql += " ORDER BY rating DESC, discount_pct DESC"
    elif section == "donate":
        sql += " AND product_type='game' AND category_id IN (SELECT id FROM categories WHERE slug IN ('currency','dlc'))"
        sql += " ORDER BY rating DESC"
    elif sort == "discount":
        sql += " AND product_type='game'"
        sql += " ORDER BY discount_pct DESC, is_featured DESC, rating DESC"
    else:
        sql += " ORDER BY is_featured DESC, rating DESC"

    sql += " LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = await db.execute_fetchall(sql, params)
    products = [dict(r) for r in rows]
    products = await _attach_editions(db, products)
    return products


@router.get("/featured", response_model=list[ProductOut])
async def featured_products(
    limit: int = Query(10, le=50),
    db: aiosqlite.Connection = Depends(get_db),
):
    rows = await db.execute_fetchall(
        _SELECT + " AND is_featured = 1 AND product_type='game' ORDER BY rating DESC LIMIT ?", (limit,)
    )
    products = [dict(r) for r in rows]
    products = await _attach_editions(db, products)
    return products


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(_SELECT + " AND id = ?", (product_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    products = await _attach_editions(db, [dict(row)])
    return products[0]

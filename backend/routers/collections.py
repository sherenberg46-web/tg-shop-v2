"""Public collections endpoints."""
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from backend.database import get_db
from backend.routers.products import _load_price_settings, _add_price_byn, _attach_editions

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("")
async def list_collections(db: aiosqlite.Connection = Depends(get_db)):
    """Return all active collections (no products)."""
    async with db.execute(
        """SELECT id, title, slug, description,
                  (SELECT COUNT(*) FROM collection_products WHERE collection_id = c.id) AS product_count
           FROM collections c
           WHERE is_active = 1
           ORDER BY title"""
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/{slug}")
async def get_collection(slug: str, db: aiosqlite.Connection = Depends(get_db)):
    """Return a collection with its products (prices computed)."""
    async with db.execute(
        "SELECT id, title, slug, description FROM collections WHERE slug = ? AND is_active = 1",
        (slug,),
    ) as cur:
        col = await cur.fetchone()
    if not col:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")

    s = await _load_price_settings(db)
    async with db.execute(
        """SELECT p.id, p.category_id, p.title, p.description, p.image_url,
                  p.price_uah, p.price_try, p.price_inr, p.price_pln,
                  p.platform, p.rating, p.is_featured,
                  p.discount_pct, p.discount_until,
                  p.release_date, p.product_type, p.is_preorder,
                  cp.sort_order
           FROM collection_products cp
           JOIN products p ON p.id = cp.product_id
           WHERE cp.collection_id = ? AND p.is_active = 1
           ORDER BY cp.sort_order, p.id""",
        (col["id"],),
    ) as cur:
        rows = await cur.fetchall()

    products = [dict(r) for r in rows]
    for p in products:
        _add_price_byn(p, s)
    products = await _attach_editions(db, products)

    return {
        "id": col["id"],
        "title": col["title"],
        "slug": col["slug"],
        "description": col["description"],
        "products": products,
    }

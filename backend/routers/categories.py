from fastapi import APIRouter, Depends
import aiosqlite
from backend.database import get_db
from backend.schemas import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: aiosqlite.Connection = Depends(get_db)):
    rows = await db.execute_fetchall(
        "SELECT id, name, slug, icon, sort_order FROM categories ORDER BY sort_order"
    )
    return [dict(r) for r in rows]


@router.get("/{slug}", response_model=CategoryOut)
async def get_category(slug: str, db: aiosqlite.Connection = Depends(get_db)):
    from fastapi import HTTPException
    async with db.execute(
        "SELECT id, name, slug, icon, sort_order FROM categories WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")
    return dict(row)

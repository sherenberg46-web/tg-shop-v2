"""Public banners endpoint — no auth required."""
from fastapi import APIRouter, Depends
import aiosqlite
from backend.database import get_db

router = APIRouter(prefix="/banners", tags=["banners"])


@router.get("")
async def list_banners_public(db: aiosqlite.Connection = Depends(get_db)):
    """Return active banners ordered by sort_order for the HeroBanner component."""
    async with db.execute(
        """SELECT id, title, subtitle, image_url,
                  link_ua, link_tr, link_url, gradient, sort_order, collection_slug
           FROM admin_banners
           WHERE is_active = 1
           ORDER BY sort_order ASC, id ASC"""
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

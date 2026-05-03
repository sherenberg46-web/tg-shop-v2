"""Public settings endpoint — no auth, used by the frontend for price calculation."""
from fastapi import APIRouter, Depends
import aiosqlite
from backend.database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS = {
    "uah_rate":        "0.069",
    "try_rate":        "0.07",
    "uah_markup_500":  "70",
    "uah_markup_1000": "60",
    "uah_markup_1500": "50",
    "uah_markup_2000": "40",
    "uah_markup_max":  "30",
    "try_markup_500":  "70",
    "try_markup_1000": "60",
    "try_markup_1500": "50",
    "try_markup_2000": "40",
    "try_markup_max":  "30",
}


@router.get("")
async def get_public_settings(db: aiosqlite.Connection = Depends(get_db)):
    """Return current price settings (rates + markup tiers) for frontend use."""
    try:
        async with db.execute("SELECT key, value FROM admin_settings") as cur:
            rows = await cur.fetchall()
        result = dict(DEFAULTS)
        for r in rows:
            if r["key"] in DEFAULTS:
                result[r["key"]] = r["value"]
        # Convert string values to numbers for easy frontend use
        return {k: float(v) for k, v in result.items()}
    except Exception:
        return {k: float(v) for k, v in DEFAULTS.items()}

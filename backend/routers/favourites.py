import math
from fastapi import APIRouter, Depends, HTTPException, Header
import aiosqlite
from backend.database import get_db
from backend.schemas import ProductOut, MessageOut

router = APIRouter(prefix="/favourites", tags=["favourites"])

_UAH_TO_BYN = 0.069
_TRY_TO_BYN = 0.09


def _uah_to_byn(uah: float) -> int:
    if uah <= 0:
        return 0
    if uah > 2000:
        return math.ceil(uah * 0.1)
    if uah <= 500:
        markup = 1.70
    elif uah <= 1000:
        markup = 1.60
    elif uah <= 1500:
        markup = 1.50
    else:
        markup = 1.40
    return math.ceil(uah * _UAH_TO_BYN * markup)


def _try_to_byn(try_price: float) -> int:
    if try_price <= 0:
        return 0
    if try_price > 2000:
        return math.ceil(try_price * 0.1)
    if try_price <= 500:
        markup = 1.70
    elif try_price <= 1000:
        markup = 1.60
    elif try_price <= 1500:
        markup = 1.50
    else:
        markup = 1.40
    return math.ceil(try_price * _TRY_TO_BYN * markup)


def _add_price_byn(product: dict) -> dict:
    pt = product.get("product_type", "game")
    price_uah = product.get("price_uah") or 0
    price_try = product.get("price_try") or 0
    if pt in ("subscription", "topup"):
        product["price_byn"] = int(price_uah) if price_uah > 0 else None
        product["price_byn_tr"] = None
    else:
        product["price_byn"] = _uah_to_byn(price_uah) if price_uah > 0 else None
        product["price_byn_tr"] = _try_to_byn(price_try) if price_try > 0 else None
    return product


def _require_user(x_user_id: str | None = Header(None)) -> int:
    if not x_user_id or not x_user_id.isdigit():
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return int(x_user_id)


@router.get("", response_model=list[ProductOut])
async def list_favourites(
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    rows = await db.execute_fetchall(
        """SELECT p.id, p.category_id, p.title, p.description, p.image_url,
                  p.price_uah, p.price_try, p.price_inr, p.price_pln,
                  p.platform, p.rating, p.is_featured,
                  p.discount_pct, p.discount_until,
                  p.release_date, p.product_type, p.is_preorder
           FROM favourites f
           JOIN products p ON p.id = f.product_id
           WHERE f.user_id = ? AND p.is_active = 1""",
        (user_id,),
    )
    return [_add_price_byn(dict(r)) for r in rows]


@router.post("/{product_id}", response_model=MessageOut, status_code=201)
async def add_favourite(
    product_id: int,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    await db.execute(
        "INSERT OR IGNORE INTO favourites (user_id, product_id) VALUES (?,?)",
        (user_id, product_id),
    )
    await db.commit()
    return {"message": "Added to favourites"}


@router.delete("/{product_id}", response_model=MessageOut)
async def remove_favourite(
    product_id: int,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute(
        "DELETE FROM favourites WHERE user_id = ? AND product_id = ?",
        (user_id, product_id),
    )
    await db.commit()
    return {"message": "Removed from favourites"}

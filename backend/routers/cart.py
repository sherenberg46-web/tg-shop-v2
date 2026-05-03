"""Cart endpoints – stored server-side per Telegram user_id."""
import math
from fastapi import APIRouter, Depends, HTTPException, Header
import aiosqlite
from backend.database import get_db
from backend.schemas import CartItemIn, CartItemOut, MessageOut

router = APIRouter(prefix="/cart", tags=["cart"])

PRICE_COL = {"UA": "price_uah", "TR": "price_try", "IN": "price_inr", "PL": "price_pln"}
_UAH_TO_BYN = 0.069
_TRY_TO_BYN = 0.09


def _uah_to_byn(price_uah: float) -> float:
    """Convert UAH price to BYN using tiered markup."""
    if price_uah <= 0:
        return 0
    if price_uah > 2000:
        return math.ceil(price_uah * 0.1)
    if price_uah <= 500:
        markup = 1.70
    elif price_uah <= 1000:
        markup = 1.60
    elif price_uah <= 1500:
        markup = 1.50
    else:
        markup = 1.40
    return math.ceil(price_uah * _UAH_TO_BYN * markup)


def _try_to_byn(price_try: float) -> float:
    """Convert TRY price to BYN using tiered markup."""
    if price_try <= 0:
        return 0
    if price_try > 2000:
        return math.ceil(price_try * 0.1)
    if price_try <= 500:
        markup = 1.70
    elif price_try <= 1000:
        markup = 1.60
    elif price_try <= 1500:
        markup = 1.50
    else:
        markup = 1.40
    return math.ceil(price_try * _TRY_TO_BYN * markup)


def _price_to_byn(raw: float, region: str, ptype: str) -> float:
    """Convert a price in the given region's currency to BYN."""
    if not raw:
        return 0
    if ptype in ("subscription", "topup"):
        # For these types, price_uah already stores the BYN value directly
        return float(raw)
    if region == "TR":
        return _try_to_byn(raw)
    return _uah_to_byn(raw)


def _require_user(x_user_id: str | None = Header(None)) -> int:
    if not x_user_id or not x_user_id.isdigit():
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return int(x_user_id)


async def _ensure_user(user_id: int, db: aiosqlite.Connection) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,)
    )
    await db.commit()


@router.get("", response_model=list[CartItemOut])
async def get_cart(
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    rows = await db.execute_fetchall(
        """SELECT c.id, c.product_id, c.quantity, c.region,
                  p.title, p.image_url,
                  p.price_uah, p.price_try, p.price_inr, p.price_pln,
                  p.product_type
           FROM cart_items c
           JOIN products p ON p.id = c.product_id
           WHERE c.user_id = ?""",
        (user_id,),
    )
    result = []
    for r in rows:
        ptype = r["product_type"] or "game"
        col = PRICE_COL.get(r["region"], "price_uah")
        raw = r[col] or 0
        price_byn = _price_to_byn(raw, r["region"], ptype) if raw else None
        result.append(
            CartItemOut(
                id=r["id"],
                product_id=r["product_id"],
                quantity=r["quantity"],
                region=r["region"],
                title=r["title"],
                image_url=r["image_url"],
                price=price_byn,
            )
        )
    return result


@router.post("", response_model=MessageOut, status_code=201)
async def add_to_cart(
    item: CartItemIn,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    await _ensure_user(user_id, db)

    async with db.execute("SELECT id FROM products WHERE id = ? AND is_active = 1", (item.product_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")

    await db.execute(
        """INSERT INTO cart_items (user_id, product_id, quantity, region)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, product_id, region)
           DO UPDATE SET quantity = quantity + excluded.quantity""",
        (user_id, item.product_id, item.quantity, item.region),
    )
    await db.commit()
    return {"message": "Added to cart"}


@router.put("/{item_id}", response_model=MessageOut)
async def update_cart_item(
    item_id: int,
    quantity: int,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    if quantity <= 0:
        await db.execute(
            "DELETE FROM cart_items WHERE id = ? AND user_id = ?", (item_id, user_id)
        )
    else:
        await db.execute(
            "UPDATE cart_items SET quantity = ? WHERE id = ? AND user_id = ?",
            (quantity, item_id, user_id),
        )
    await db.commit()
    return {"message": "Cart updated"}


@router.delete("/{item_id}", response_model=MessageOut)
async def remove_from_cart(
    item_id: int,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?", (item_id, user_id)
    )
    await db.commit()
    return {"message": "Removed from cart"}


@router.delete("", response_model=MessageOut)
async def clear_cart(
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    await db.commit()
    return {"message": "Cart cleared"}

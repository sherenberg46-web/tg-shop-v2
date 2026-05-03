"""Order endpoints."""
import math
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
from datetime import datetime
import httpx
import logging
import aiosqlite
from backend.config import settings
from backend.database import get_db
from backend.schemas import OrderIn, OrderOut, OrderItemOut, MessageOut

log = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])

PRICE_COL = {"UA": "price_uah", "TR": "price_try", "IN": "price_inr", "PL": "price_pln"}

_UAH_TO_BYN = 0.069
_TRY_TO_BYN = 0.09


def _uah_to_byn(price_uah: float) -> float:
    """UAH → BYN with tiered markup."""
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
    """TRY → BYN with tiered markup."""
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


def _price_to_byn(raw: float, region: str, product_type: str) -> float:
    """Convert a price in the given region's currency to BYN."""
    if raw <= 0:
        return 0
    if product_type in ("subscription", "topup"):
        # For these types, price_uah already stores the BYN value directly
        return float(raw)
    if region == "TR":
        return _try_to_byn(raw)
    return _uah_to_byn(raw)


def _require_user(x_user_id: str | None = Header(None)) -> int:
    if not x_user_id or not x_user_id.isdigit():
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return int(x_user_id)


async def _notify_manager(order_id: int, enriched: list, body: OrderIn, total_byn: float) -> None:
    """Send new-order notification to admin via Telegram Bot API."""
    if not settings.BOT_TOKEN:
        log.warning("_notify_manager: BOT_TOKEN not set, skipping notification")
        return
    if not settings.ADMIN_ID:
        log.warning("_notify_manager: ADMIN_ID not set, skipping notification")
        return

    try:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        items_lines = "\n".join(
            f"  • {e[1]} ×{e[2]} [{e[4]}]" for e in enriched
        )

        # Build buyer display string
        if body.first_name or body.username:
            name_part = body.first_name or ""
            user_part = f"@{body.username}" if body.username else f"<a href='tg://user?id={body.user_id}'>#{body.user_id}</a>"
            buyer = f"{name_part} {user_part}".strip()
        else:
            buyer = f"<a href='tg://user?id={body.user_id}'>#{body.user_id}</a>"

        text = (
            f"🛒 <b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n\n"
            f"👤 {buyer}\n"
            f"🌍 Регион: {body.region}\n"
            f"📅 {now}\n\n"
            f"📦 Товары:\n{items_lines}\n\n"
            f"💰 Итого: <b>{total_byn:.2f} BYN</b>\n"
        )
        if body.account_type == "my_account" and body.ps_email:
            text += (
                f"\n📧 Email PS: <code>{body.ps_email}</code>\n"
                f"🔑 Пароль PS: <code>{body.ps_password or '—'}</code>\n"
            )
        else:
            text += "\n⚠️ Нужно создать новый аккаунт\n"

        recipients = [settings.ADMIN_ID]
        if settings.MANAGER_CHAT_ID and settings.MANAGER_CHAT_ID != settings.ADMIN_ID:
            recipients.append(settings.MANAGER_CHAT_ID)

        async with httpx.AsyncClient() as client:
            for chat_id in recipients:
                log.info("Sending order #%d notification to %s", order_id, chat_id)
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    log.info("Order #%d notification sent OK to %s", order_id, chat_id)
                else:
                    log.error("Telegram API error %s for chat %s: %s", resp.status_code, chat_id, resp.text)
    except Exception as exc:
        log.error("_notify_manager failed for order #%d: %s", order_id, exc)


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderIn,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute(
        """INSERT INTO users (id, username, first_name) VALUES (?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             username   = COALESCE(excluded.username,    username),
             first_name = COALESCE(excluded.first_name,  first_name)""",
        (body.user_id, body.username, body.first_name),
    )

    price_col = PRICE_COL.get(body.region, "price_uah")
    total_byn = 0.0
    enriched = []

    for item in body.items:
        async with db.execute(
            f"SELECT id, title, {price_col} as price, product_type"
            f" FROM products WHERE id = ? AND is_active = 1",
            (item.product_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        price = row["price"] or 0
        ptype = row["product_type"] or "game"
        byn = _price_to_byn(price, body.region, ptype)
        total_byn += byn * item.quantity
        enriched.append((item.product_id, row["title"], item.quantity, byn, body.region))

    async with db.execute(
        """INSERT INTO orders (user_id, status, total_stars, account_type, ps_email, ps_password)
           VALUES (?, 'pending', ?, ?, ?, ?)""",
        (body.user_id, int(total_byn),
         body.account_type or "no_account", body.ps_email, body.ps_password),
    ) as cur:
        order_id = cur.lastrowid

    await db.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, price_paid, region) VALUES (?,?,?,?,?)",
        [(order_id, e[0], e[2], e[3], e[4]) for e in enriched],
    )
    await db.commit()

    background_tasks.add_task(_notify_manager, order_id, enriched, body, total_byn)

    return OrderOut(
        id=order_id,
        user_id=body.user_id,
        status="pending",
        total_byn=round(total_byn, 2),
        items=[
            OrderItemOut(product_id=e[0], title=e[1], quantity=e[2], price_paid=e[3], region=e[4])
            for e in enriched
        ],
        created_at="",
        account_type=body.account_type or "no_account",
        ps_email=body.ps_email,
        ps_password=body.ps_password,
    )


@router.get("/my", response_model=list[OrderOut])
async def my_orders(
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    """List all orders for the authenticated user (newest first)."""
    async with db.execute(
        """SELECT id, user_id, status, total_stars, created_at,
                  account_type, ps_email, ps_password
           FROM orders WHERE user_id = ? ORDER BY created_at DESC""",
        (user_id,),
    ) as cur:
        orders = await cur.fetchall()

    result = []
    for order in orders:
        rows = await db.execute_fetchall(
            """SELECT oi.product_id, p.title, oi.quantity, oi.price_paid, oi.region
               FROM order_items oi JOIN products p ON p.id = oi.product_id
               WHERE oi.order_id = ?""",
            (order["id"],),
        )
        result.append(OrderOut(
            id=order["id"],
            user_id=order["user_id"],
            status=order["status"],
            total_byn=float(order["total_stars"]),
            created_at=order["created_at"] or "",
            items=[OrderItemOut(**dict(r)) for r in rows],
            account_type=order["account_type"],
            ps_email=order["ps_email"],
            ps_password=order["ps_password"],
        ))
    return result


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    user_id: int = Depends(_require_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute(
        """SELECT id, user_id, status, total_stars, created_at,
                  account_type, ps_email, ps_password
           FROM orders WHERE id = ? AND user_id = ?""",
        (order_id, user_id),
    ) as cur:
        order = await cur.fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    rows = await db.execute_fetchall(
        """SELECT oi.product_id, p.title, oi.quantity, oi.price_paid, oi.region
           FROM order_items oi JOIN products p ON p.id = oi.product_id
           WHERE oi.order_id = ?""",
        (order_id,),
    )
    return OrderOut(
        id=order["id"],
        user_id=order["user_id"],
        status=order["status"],
        total_byn=float(order["total_stars"]),
        created_at=order["created_at"],
        items=[OrderItemOut(**dict(r)) for r in rows],
        account_type=order["account_type"],
        ps_email=order["ps_email"],
        ps_password=order["ps_password"],
    )


@router.post("/{order_id}/complete", response_model=MessageOut)
async def complete_order(
    order_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    await db.execute(
        "UPDATE orders SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (order_id,),
    )
    await db.commit()
    return {"message": "Order completed"}

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite
from backend.database import get_db
from backend.schemas import ProductOut, EditionOut, GameEditionOut

_CONCEPT_RE = re.compile(r'^([A-Z]{2}\d+-[A-Z]{2,4}\d+)_\d{2}-', re.IGNORECASE)

def _extract_concept(original_id: str | None) -> str | None:
    """Extract PS Store concept ID from product original_id."""
    if not original_id:
        return None
    m = _CONCEPT_RE.match(original_id)
    return m.group(1).upper() if m else None


# Edition suffix patterns used to find the base title of a game
_EDITION_SUFFIX_RE = re.compile(
    r'[\s:]+[-–]?\s*(?:Digital\s+)?'
    r'(?:Standard|Deluxe|Ultimate|Gold|Complete|Premium|Champions|Legend|Legendary|'
    r'Platinum|Diamond|Silver|Bronze|Special|Definitive|Enhanced|Remastered|'
    r"Director'?s\s+Cut|Anniversary|Collector'?s?|Founder'?s?)"
    r'(?:\s+Edition)?'
    r'\s*$',
    re.IGNORECASE,
)


def _base_title(title: str) -> str:
    """Strip edition qualifier to get the base game title."""
    return _EDITION_SUFFIX_RE.sub('', title).strip()


def _are_edition_pair(t1: str, t2: str) -> bool:
    """True if two titles belong to the same game (one is an edition of the other)."""
    if t1.lower() == t2.lower():
        return True
    b1, b2 = _base_title(t1).lower(), _base_title(t2).lower()
    return bool(b1) and b1 == b2

router = APIRouter(prefix="/products", tags=["products"])

MIN_PRICE_BYN = 10  # floor: no product shown for less than 10 BYN


# ── Price settings (loaded from admin_settings table) ─────────────

@dataclass
class PriceSettings:
    uah_rate: float = 0.069
    try_rate: float = 0.07
    # Markup multipliers per tier (price ≤ tier boundary)
    # Tiers: ≤500, ≤1000, ≤1500, ≤2000, >2000
    uah_markups: tuple = (1.70, 1.60, 1.50, 1.40, 1.30)
    try_markups: tuple = (1.70, 1.60, 1.50, 1.40, 1.30)


_DEFAULTS = PriceSettings()


async def _load_price_settings(db: aiosqlite.Connection) -> PriceSettings:
    """Read price settings from admin_settings. Falls back to defaults."""
    try:
        async with db.execute("SELECT key, value FROM admin_settings") as cur:
            rows = await cur.fetchall()
        kv = {r["key"]: r["value"] for r in rows}

        def flt(key: str, default: float) -> float:
            try:
                return float(kv[key])
            except (KeyError, ValueError, TypeError):
                return default

        return PriceSettings(
            uah_rate=flt("uah_rate", 0.069),
            try_rate=flt("try_rate", 0.07),
            uah_markups=(
                1 + flt("uah_markup_500",  70) / 100,
                1 + flt("uah_markup_1000", 60) / 100,
                1 + flt("uah_markup_1500", 50) / 100,
                1 + flt("uah_markup_2000", 40) / 100,
                1 + flt("uah_markup_max",  30) / 100,
            ),
            try_markups=(
                1 + flt("try_markup_500",  70) / 100,
                1 + flt("try_markup_1000", 60) / 100,
                1 + flt("try_markup_1500", 50) / 100,
                1 + flt("try_markup_2000", 40) / 100,
                1 + flt("try_markup_max",  30) / 100,
            ),
        )
    except Exception:
        return _DEFAULTS


def _uah_to_byn(uah: float, s: PriceSettings) -> int:
    if uah <= 0:
        return 0
    byn_base = uah * s.uah_rate
    if uah <= 500:
        m = s.uah_markups[0]
    elif uah <= 1000:
        m = s.uah_markups[1]
    elif uah <= 1500:
        m = s.uah_markups[2]
    elif uah <= 2000:
        m = s.uah_markups[3]
    else:
        m = s.uah_markups[4]
    return math.ceil(byn_base * m)


def _try_to_byn(try_price: float, s: PriceSettings) -> int:
    if try_price <= 0:
        return 0
    byn_base = try_price * s.try_rate
    if try_price <= 500:
        m = s.try_markups[0]
    elif try_price <= 1000:
        m = s.try_markups[1]
    elif try_price <= 1500:
        m = s.try_markups[2]
    elif try_price <= 2000:
        m = s.try_markups[3]
    else:
        m = s.try_markups[4]
    return math.ceil(byn_base * m)


def _clamp(price: int | None) -> int | None:
    if price is None:
        return None
    return max(price, MIN_PRICE_BYN)


def _add_price_byn(product: dict, s: PriceSettings) -> dict:
    pt = product.get("product_type", "game")
    price_uah = product.get("price_uah") or 0
    price_try = product.get("price_try") or 0
    # Respect manual admin overrides stored in DB columns
    manual_byn    = product.get("price_byn")
    manual_byn_tr = product.get("price_byn_tr")
    if pt in ("subscription", "topup"):
        product["price_byn"]    = manual_byn if manual_byn is not None else (int(price_uah) if price_uah > 0 else None)
        product["price_byn_tr"] = manual_byn_tr
    else:
        # price_byn: prefer UAH source; fall back to TRY when there's no UAH price
        if price_uah > 0:
            new_byn = _clamp(_uah_to_byn(price_uah, s))
        elif price_try > 0:
            new_byn = _clamp(_try_to_byn(price_try, s))
        else:
            new_byn = None
        product["price_byn"]    = manual_byn    if manual_byn    is not None else new_byn
        product["price_byn_tr"] = manual_byn_tr if manual_byn_tr is not None else _clamp(_try_to_byn(price_try, s) if price_try > 0 else None)
    return product


_SELECT = """
    SELECT id, category_id, title, description, image_url,
           price_uah, price_try, price_inr, price_pln,
           price_byn, price_byn_tr,
           platform, rating, is_featured,
           discount_pct, discount_until,
           release_date, product_type, is_preorder,
           task_type, region, genre, requires_ps_plus
    FROM products
    WHERE is_active = 1
"""


async def _attach_editions(db: aiosqlite.Connection, products: list[dict]) -> list[dict]:
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


def _process(products: list[dict], s: PriceSettings) -> list[dict]:
    for p in products:
        _add_price_byn(p, s)
    return products


@router.get("", response_model=list[ProductOut])
async def list_products(
    category_id: int | None = Query(None),
    featured: bool | None = Query(None),
    search: str | None = Query(None, min_length=2),
    section: str | None = Query(None),
    product_type: str | None = Query(None),
    sort: str | None = Query(None),
    region: str | None = Query(None),
    task_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
):
    s = await _load_price_settings(db)
    sql, params = _SELECT, []
    today = date.today().isoformat()
    cutoff_90 = (date.today() - timedelta(days=90)).isoformat()

    # new_games always shows UA products (which carry both UA and TR pricing).
    # All other sections respect the requested region.
    if region and task_type != "new_games":
        sql += " AND region = ?"
        params.append(region.upper())

    # task_type: match parser-tagged products OR equivalent data-based criteria
    order_by = ""
    if task_type == "sales":
        sql += " AND (task_type = 'sales' OR discount_pct > 0) AND product_type = 'game'"
        order_by = " ORDER BY discount_pct DESC, is_featured DESC, rating DESC"
    elif task_type == "preorders":
        sql += " AND (task_type = 'preorders' OR is_preorder = 1) AND product_type = 'game'"
        order_by = " ORDER BY COALESCE(release_date, '9999-99-99') ASC, rating DESC"
    elif task_type == "new_games":
        sql += (
            " AND task_type = 'new_games'"
            " AND product_type = 'game' AND is_preorder = 0"
            " AND region = 'UA'"  # UA products carry both UA and TR prices for all users
            " AND (release_date IS NULL OR release_date >= '2022-01-01')"
        )
        # Games without release_date (FC 26, STALKER 2 etc.) sort first; then by release_date DESC
        order_by = " ORDER BY COALESCE(release_date, '9999-99-99') DESC, is_featured DESC, rating DESC"
    elif task_type:
        sql += " AND task_type = ?"
        params.append(task_type)

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

    if order_by:
        sql += order_by
    elif section == "new":
        sql += " AND product_type='game' AND is_preorder=0 AND release_date IS NOT NULL AND release_date >= ? AND release_date <= ?"
        params += [cutoff_90, today]
        sql += " ORDER BY release_date DESC, is_featured DESC, rating DESC, price_uah DESC"
    elif section == "releases":
        cutoff_near = (date.today() - timedelta(days=365)).isoformat()
        sql += " AND product_type='game' AND is_preorder=0 AND release_date IS NOT NULL AND release_date >= ? AND release_date < ?"
        params += [cutoff_near, cutoff_90]
        sql += " ORDER BY release_date DESC"
    elif section == "preorder":
        sql += " AND product_type='game' AND is_preorder = 1"
        sql += " ORDER BY COALESCE(release_date, '9999-99-99') ASC, rating DESC"
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
    products = _process([dict(r) for r in rows], s)
    products = await _attach_editions(db, products)
    return products


@router.get("/featured", response_model=list[ProductOut])
async def featured_products(
    limit: int = Query(10, le=50),
    db: aiosqlite.Connection = Depends(get_db),
):
    s = await _load_price_settings(db)
    rows = await db.execute_fetchall(
        _SELECT + " AND is_featured = 1 AND product_type='game' ORDER BY rating DESC LIMIT ?", (limit,)
    )
    products = _process([dict(r) for r in rows], s)
    products = await _attach_editions(db, products)
    return products


@router.get("/{product_id}/editions", response_model=list[GameEditionOut])
async def get_product_editions(
    product_id: int,
    region: str = Query("UA"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Return editions for a product.
    Priority:
      1. game_editions table (parser-sourced SKU data)
      2. Concept-based siblings: other products sharing the same PS Store concept ID
    """
    rgn = region.upper()

    # 1. Try game_editions
    rows = await db.execute_fetchall(
        """SELECT id, edition_name, price_uah, price_try, price_byn, price_byn_tr,
                  old_price_uah, old_price_try, discount_pct, platform,
                  ps_store_url, region, is_free
           FROM game_editions
           WHERE parent_product_id = ? AND region = ? AND is_active = 1
           ORDER BY sort_order, id""",
        (product_id, rgn),
    )
    if rows:
        return [dict(r) for r in rows]

    # 2. Get current product meta
    async with db.execute(
        "SELECT original_id, title, category_id FROM products WHERE id = ?", (product_id,)
    ) as cur:
        prow = await cur.fetchone()
    if not prow:
        return []

    # Helper: turn a sibling product row into GameEditionOut dict
    def _sibling_dict(s: dict) -> dict:
        return {
            "id":                s["id"],
            "edition_name":      s["title"],
            "price_uah":         s["price_uah"],
            "price_try":         s["price_try"],
            "price_byn":         s["price_byn"],
            "price_byn_tr":      s["price_byn_tr"],
            "old_price_uah":     None,
            "old_price_try":     None,
            "discount_pct":      int(s["discount_pct"] or 0),
            "platform":          s["platform"],
            "ps_store_url":      None,
            "region":            rgn,
            "is_free":           False,
            "linked_product_id": s["id"],
        }

    ps = await _load_price_settings(db)

    _SIBLING_SELECT = """
        SELECT id, title, price_uah, price_try, price_byn, price_byn_tr,
               discount_pct, platform, product_type
        FROM products
        WHERE region = ? AND is_active = 1
    """

    def _priced_siblings(rows) -> list[dict]:
        result = []
        for r in rows:
            d = dict(r)
            _add_price_byn(d, ps)
            result.append(_sibling_dict(d))
        return result

    title = prow["title"] or ""

    # 3. Concept-based fallback (works when original_id is populated)
    concept = _extract_concept(prow["original_id"])
    if concept:
        concept_rows = await db.execute_fetchall(
            _SIBLING_SELECT + " AND original_id GLOB ? ORDER BY id",
            (rgn, concept + "_*"),
        )
        # Filter to real edition pairs — DLC packs share a concept ID but are not editions
        edition_siblings = [dict(r) for r in concept_rows if _are_edition_pair(title, r["title"])]
        if len(edition_siblings) >= 2:
            return _priced_siblings(edition_siblings)

    # 4. Title-prefix fallback: "PRAGMATA" ↔ "PRAGMATA Deluxe Edition"
    base = _base_title(title)
    first_word = (base or title).split()[0] if (base or title) else ""
    if not first_word:
        return []

    candidates = await db.execute_fetchall(
        _SIBLING_SELECT + " AND title LIKE ? ORDER BY LENGTH(title) ASC, id LIMIT 50",
        (rgn, first_word + "%"),
    )
    siblings = [dict(r) for r in candidates if _are_edition_pair(title, r["title"])]
    if len(siblings) >= 2:
        return _priced_siblings(siblings)

    return []


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    s = await _load_price_settings(db)
    async with db.execute(_SELECT + " AND id = ?", (product_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    products = _process([dict(row)], s)
    products = await _attach_editions(db, products)
    return products[0]

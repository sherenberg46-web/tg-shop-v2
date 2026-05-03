"""
Parser configuration.

Exchange rates and markups are NOT hardcoded here — they live in the
admin_settings table (same source as the backend). Use get_price_settings()
to load them before doing any price calculation.

The only static values here are infrastructure settings (paths, tokens,
PS Store API constants) that never change at runtime.
"""
import math
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env: project root first, then parser/.env overrides (so parser can have its own password/proxy)
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")
load_dotenv(Path(__file__).parent / ".env", override=True)

# ── Database ──────────────────────────────────────────────────────────────────
# Must match backend DB_PATH (Settings.DB_PATH default = "database/shop.db")
DB_PATH = Path(os.environ.get("DB_PATH", "database/shop.db"))
if not DB_PATH.is_absolute():
    DB_PATH = _root / DB_PATH

# ── Proxy ─────────────────────────────────────────────────────────────────────
PROXY_URL: str = os.environ.get("PROXY_URL", "")

# ── Admin password ────────────────────────────────────────────────────────────
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin1234")

# ── PS Store GraphQL ──────────────────────────────────────────────────────────
PS_GRAPHQL    = "https://web.np.playstation.com/api/graphql/v1/op"
STRAND_SHA256 = "5426f8d7515b00e0bff77e6e6905d7ecb8b20e4495c14ec424cf21676e7e73e1"
GRID_SHA256   = "9845afc0dbaab4965f6563fffc703f588c8e76792000e8610843b8d3ee9c4c09"

# ── PS Store category IDs ─────────────────────────────────────────────────────
PS_CATEGORIES = {
    "ps5_games": "44d8bb20-653e-431e-8ad0-c0a365f68d2f",
    "ps4_games": "4cbf39e2-5749-4970-ba81-93a489e4570c",
}
DEALS_CATEGORY_ID     = "3f772501-f6f8-49b7-abac-874a88ca4897"
NEW_GAMES_CATEGORY_ID = "e1699f77-77e1-43ca-a296-26d08abacb0f"
PREORDERS_CATEGORY_ID = "3bf499d7-7acf-4931-97dd-2667494ee2c9"

# ── DB categories ─────────────────────────────────────────────────────────────
STORE_CATEGORIES = [
    ("ps-games",   "PS Games"),
    ("ps-plus",    "PS Plus"),
    ("ea-play",    "EA Play"),
    ("gift-cards", "Карты пополнения"),
    ("dlc",        "DLC"),
    ("currency",   "Игровая валюта"),
]

# ── BYN price floor (same as backend MIN_PRICE_BYN) ──────────────────────────
MIN_PRICE_BYN = 10


# ── Price settings — identical dataclass to backend/routers/products.py ───────

@dataclass
class PriceSettings:
    uah_rate: float = 0.069
    try_rate: float = 0.07
    # Markup multipliers per tier (≤500, ≤1000, ≤1500, ≤2000, >2000)
    # Stored in admin_settings as percentages (e.g. "70" → 1.70)
    uah_markups: tuple = (1.70, 1.60, 1.50, 1.40, 1.30)
    try_markups: tuple = (1.70, 1.60, 1.50, 1.40, 1.30)


# Hardcoded defaults — only used when admin_settings table is empty/missing
_DEFAULTS = PriceSettings()


async def get_price_settings(conn) -> PriceSettings:
    """
    Load price settings from admin_settings table.
    Mirrors backend/_load_price_settings() exactly — same keys, same defaults,
    same markup-% → multiplier conversion.
    """
    try:
        async with conn.execute("SELECT key, value FROM admin_settings") as cur:
            rows = await cur.fetchall()
        kv = {r[0]: r[1] for r in rows}

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


# ── Price conversion — identical to backend/routers/products.py ───────────────

def uah_to_byn(uah: float, s: PriceSettings) -> int:
    """
    Convert UAH → BYN:
      1. byn_base = uah × uah_rate
      2. markup tier selected from source UAH price (≤500/1000/1500/2000/>2000 UAH)
      3. result = math.ceil(byn_base × markup)
    """
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


def try_to_byn(try_price: float, s: PriceSettings) -> int:
    """
    Convert TRY → BYN:
      1. byn_base = try_price × try_rate
      2. markup tier selected from source TRY price (≤500/1000/1500/2000/>2000 TRY)
      3. result = math.ceil(byn_base × markup)
    """
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


def clamp_byn(price: int | None) -> int | None:
    """Apply MIN_PRICE_BYN floor. Same as backend _clamp()."""
    if price is None:
        return None
    return max(price, MIN_PRICE_BYN)


def calc_price_byn(product: dict, s: PriceSettings) -> dict:
    """
    Fill price_byn / price_byn_tr on a product dict.
    Logic is identical to backend _add_price_byn():
      - Manual overrides (non-None price_byn/price_byn_tr columns) take priority.
      - subscription/topup: price_uah IS the BYN price already.
      - games: convert from UAH→BYN or TRY→BYN with tiered markup.
    """
    pt         = product.get("product_type", "game")
    price_uah  = product.get("price_uah") or 0
    price_try  = product.get("price_try") or 0
    manual_byn    = product.get("price_byn")
    manual_byn_tr = product.get("price_byn_tr")

    if pt in ("subscription", "topup"):
        product["price_byn"]    = manual_byn if manual_byn is not None else (int(price_uah) if price_uah > 0 else None)
        product["price_byn_tr"] = manual_byn_tr
    else:
        # price_byn: prefer UAH source; fall back to TRY when there's no UAH price
        if price_uah > 0:
            new_byn = clamp_byn(uah_to_byn(price_uah, s))
        elif price_try > 0:
            new_byn = clamp_byn(try_to_byn(price_try, s))
        else:
            new_byn = None
        product["price_byn"]    = manual_byn    if manual_byn    is not None else new_byn
        product["price_byn_tr"] = manual_byn_tr if manual_byn_tr is not None else clamp_byn(try_to_byn(price_try, s) if price_try > 0 else None)

    return product

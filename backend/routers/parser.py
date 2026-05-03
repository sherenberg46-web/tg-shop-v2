"""
PS Store Parser + Fixed-price subscriptions & top-up cards.
Endpoint: POST /api/v1/parser/parse
Uses categoryStrandRetrieve operation (same as browser) with proper headers.
"""
import asyncio
import json
import math
import os
import re
import logging
import uuid
import httpx
import aiosqlite
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from sse_starlette.sse import EventSourceResponse
from backend.config import settings
from backend.database import get_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/parser", tags=["parser"])

UAH_TO_BYN = 0.069

def uah_to_byn(price_uah: float) -> float:
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
    return math.ceil(price_uah * UAH_TO_BYN * markup)


PS_GRAPHQL = "https://web.np.playstation.com/api/graphql/v1/op"
STRAND_SHA256 = "5426f8d7515b00e0bff77e6e6905d7ecb8b20e4495c14ec424cf21676e7e73e1"
GRID_SHA256 = "9845afc0dbaab4965f6563fffc703f588c8e76792000e8610843b8d3ee9c4c09"

PS_CATEGORIES = {
    "ps5_games": "44d8bb20-653e-431e-8ad0-c0a365f68d2f",
    "ps4_games": "4cbf39e2-5749-4970-ba81-93a489e4570c",
}

DEALS_CATEGORY_ID     = "3f772501-f6f8-49b7-abac-874a88ca4897"
NEW_GAMES_CATEGORY_ID = "e1699f77-77e1-43ca-a296-26d08abacb0f"
PREORDERS_CATEGORY_ID = "3bf499d7-7acf-4931-97dd-2667494ee2c9"

# Hand-curated top-10; free games (eFootball, Fortnite) are excluded.
# like_pattern: optional override for the SQL LIKE search (default: %keyword%).
# is_preorder=1 marks announced-but-not-released titles.
TOP_10_GAMES = [
    # keyword must match the DB title (via LIKE).
    # price_uah = current UA price (after discount), price_try = TR price fallback
    # (used when TR pass can't find the game — e.g. pre-orders not yet in TR store).
    {"keyword": "EA SPORTS FC 26",                     "like_pattern": "%EA SPORTS FC%26%",
     "price_uah": 2399.00, "price_try": 2499.00, "rating": 5.0, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "PRAGMATA",
     "price_uah": 2399.00, "price_try": 2499.00, "rating": 4.9, "is_preorder": 1, "discount_pct": 10,
     "search_term": "PRAGMATA"},
    {"keyword": "Crimson Desert",
     "price_uah": 1799.00, "price_try": 1899.00, "rating": 4.8, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "S.T.A.L.K.E.R. 2",                   "like_pattern": "%S.T.A.L.K.E.R%",
     "price_uah": 2449.00, "price_try": 2549.00, "rating": 4.7, "is_preorder": 0, "discount_pct": 0,
     "search_term": "STALKER 2"},
    {"keyword": "Assassin's Creed Black Flag Resynced", "like_pattern": "%Black Flag%Resynced%",
     "price_uah": 1799.00, "price_try": 1899.00, "rating": 4.6, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "Diablo IV",                           "like_pattern": "%Diablo%IV%",
     "price_uah": 3399.00, "price_try": 3499.00, "rating": 4.5, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "Metro Exodus",                        "like_pattern": "%Metro Exodus%",
     "price_uah": 1799.00, "price_try": 1899.00, "rating": 4.4, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "Call of Duty",                        "like_pattern": "%Call of Duty%",
     "price_uah": 2199.00, "price_try": 2299.00, "rating": 4.3, "is_preorder": 0, "discount_pct": 0},
    {"keyword": "Honkai: Star Rail",                   "like_pattern": "%Honkai%Star Rail%",
     "price_uah":  949.00, "price_try":  999.00, "rating": 4.2, "is_preorder": 0, "discount_pct": 0},
]

def _build_headers(country: str = "UA"):
    locale = "tr-TR" if country == "TR" else "ru-UA"
    return {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Content-Type": "application/json",
        "Origin": "https://store.playstation.com",
        "Referer": "https://store.playstation.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "Apollographql-Client-Name": "@sie-ppr-web-store/app",
        "Apollographql-Client-Version": "0.109.0",
        "X-Psn-App-Ver": "@sie-ppr-web-store/app/0.109.0-",
        "X-Psn-Store-Locale-Override": locale,
        "X-Psn-Correlation-Id": str(uuid.uuid4()),
        "X-Psn-Request-Id": str(uuid.uuid4()),
        "Cookie": f"countryCode={country}",
    }

def _get_proxy():
    proxy_url = os.environ.get("PROXY_URL", "")
    return proxy_url if proxy_url else None

async def _fetch_strand_page(client, category_id, size=12, offset=0, country="UA"):
    variables = {"id": category_id, "pageArgs": {"size": size, "offset": offset}}
    extensions = {"persistedQuery": {"version": 1, "sha256Hash": STRAND_SHA256}}
    url = f"{PS_GRAPHQL}?operationName=categoryStrandRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
    resp = await client.get(url, headers=_build_headers(country), timeout=30)
    resp.raise_for_status()
    return resp.json()

async def _fetch_grid_page(client, category_id, size=24, offset=0, country="UA"):
    variables = {"id": category_id, "pageArgs": {"size": size, "offset": offset}, "sortBy": None, "filterBy": [], "facetOptions": []}
    extensions = {"persistedQuery": {"version": 1, "sha256Hash": GRID_SHA256}}
    url = f"{PS_GRAPHQL}?operationName=categoryGridRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
    resp = await client.get(url, headers=_build_headers(country), timeout=30)
    resp.raise_for_status()
    return resp.json()

def _products_from_strand_data(strand_data):
    """Extract product list from any known categoryStrandRetrieve response shape."""
    # Format 1: direct products array
    products = strand_data.get("products") or []
    if products:
        return products, strand_data.get("pageInfo", {}).get("totalCount", len(products))
    # Format 2: strands[] → each strand has products[]
    strands = strand_data.get("strands") or []
    if strands:
        out = []
        for s in strands:
            out.extend(s.get("products") or [])
        return out, len(out)
    # Format 3: concepts[] → each concept has defaultProduct or products[]
    # concept-level fields (name, media) must be merged into the product dict
    concepts = strand_data.get("concepts") or []
    if concepts:
        out = []
        for c in concepts:
            c_name = c.get("name", "")
            c_media = c.get("media") or []
            dp = c.get("defaultProduct")
            if dp:
                merged = dict(dp)
                if not merged.get("name"):
                    merged["name"] = c_name
                if not merged.get("media"):
                    merged["media"] = c_media
                out.append(merged)
            else:
                for p in (c.get("products") or []):
                    merged = dict(p)
                    if not merged.get("name"):
                        merged["name"] = c_name
                    if not merged.get("media"):
                        merged["media"] = c_media
                    out.append(merged)
        total = strand_data.get("pageInfo", {}).get("totalCount", len(out))
        return out, total
    return [], 0

def _has_prices(products):
    """Return True if at least one product in the list has usable price data."""
    for p in products:
        pi = p.get("price") or {}
        if pi.get("basePrice") or pi.get("discountedPrice"):
            return True
        for cta in (p.get("webctas") or []):
            cpi = cta.get("price") or {}
            if cpi.get("basePrice") or cpi.get("discountedPrice"):
                return True
    return False

async def _fetch_all_games(client, category_id, max_pages=10, country="UA"):
    all_products = []
    # Try strand first
    try:
        data = await _fetch_strand_page(client, category_id, size=24, offset=0, country=country)
        strand_data = data.get("data", {}).get("categoryStrandRetrieve", {})
        products, total = _products_from_strand_data(strand_data)
        if products and _has_prices(products):
            all_products.extend(products)
            log.info("Strand cat=%s [%s]: %d products (total: %d)", category_id[:8], country, len(products), total)
            for page in range(1, max_pages):
                if len(all_products) >= total:
                    break
                try:
                    data2 = await _fetch_strand_page(client, category_id, size=24, offset=page * 24, country=country)
                    sd2 = data2.get("data", {}).get("categoryStrandRetrieve", {})
                    p2, _ = _products_from_strand_data(sd2)
                    if not p2:
                        break
                    all_products.extend(p2)
                except Exception:
                    break
            return all_products
        if products:
            log.info("Strand cat=%s [%s]: %d products but no prices, falling back to grid", category_id[:8], country, len(products))
    except Exception as e:
        log.warning("Strand [%s] failed: %s", country, e)

    # Fallback to grid
    for page in range(max_pages):
        try:
            data = await _fetch_grid_page(client, category_id, size=24, offset=page * 24, country=country)
            grid = data.get("data", {}).get("categoryGridRetrieve", {})
            products = grid.get("products", [])
            if not products:
                break
            all_products.extend(products)
            total = grid.get("pageInfo", {}).get("totalCount", 0)
            if (page + 1) * 24 >= total:
                break
        except Exception as e:
            log.error("Grid page %d [%s] failed: %s", page, country, e)
            break
    return all_products

def _parse_price_string(p):
    if not p:
        return 0
    s = str(p).replace("\xa0", "").replace(" ", "").replace("₴", "").replace("£", "").replace("$", "").replace("€", "").replace(",", ".").strip()
    if s.lower() in ("free", "бесплатно", "безкоштовно", ""):
        return 0
    s = re.sub(r'[^\d.]', '', s)
    if not s:
        return 0
    try:
        return float(s)
    except ValueError:
        return 0

def _detect_currency(price_str):
    if not price_str:
        return "unknown"
    s = str(price_str).upper()
    if "₴" in s or "ГРН" in s or "UAH" in s:
        return "UAH"
    if "₺" in s or " TL" in s or s.endswith("TL") or "TRY" in s:
        return "TRY"
    if "£" in s or "GBP" in s:
        return "GBP"
    if "$" in s or "USD" in s:
        return "USD"
    if "€" in s or "EUR" in s:
        return "EUR"
    return "unknown"

def _parse_price_try(raw) -> float:
    """Extract TRY price from a raw PS product dict (TR region response)."""
    # Try webctas first
    for cta in (raw.get("webctas") or []):
        pi = cta.get("price") or {}
        base_str = pi.get("basePrice", "")
        disc_str = pi.get("discountedPrice", "")
        cur = _detect_currency(base_str or disc_str)
        if cur != "TRY":
            continue
        dv = _parse_price_string(disc_str)
        bv = _parse_price_string(base_str)
        price = dv if dv > 0 else bv
        if price > 0:
            return price
    # Try direct price field
    price_obj = raw.get("price") or {}
    if isinstance(price_obj, dict):
        base_str = price_obj.get("basePrice", "")
        disc_str = price_obj.get("discountedPrice", "")
        if _detect_currency(base_str or disc_str) == "TRY":
            dv = _parse_price_string(disc_str)
            bv = _parse_price_string(base_str)
            price = dv if dv > 0 else bv
            if price > 0:
                return price
    return 0.0

def _parse_ps_product(raw, platform):
    try:
        name = raw.get("name", "")
        if not name:
            return None
        price_uah = 0
        discount_pct = 0
        webctas = raw.get("webctas", [])
        if webctas:
            for cta in webctas:
                pi = cta.get("price", {})
                base_str = pi.get("basePrice", "")
                disc_str = pi.get("discountedPrice", "")
                cur = _detect_currency(base_str or disc_str)
                if cur not in ("UAH", "unknown"):
                    continue
                bv = _parse_price_string(base_str)
                dv = _parse_price_string(disc_str)
                if dv > 0:
                    price_uah = dv
                    if bv > dv:
                        discount_pct = round((1 - dv / bv) * 100)
                elif bv > 0:
                    price_uah = bv
                if price_uah > 0:
                    break
        # Try direct price field (strand response format)
        if price_uah <= 0:
            price_obj = raw.get("price", {})
            if isinstance(price_obj, dict):
                base_str = price_obj.get("basePrice", "")
                disc_str = price_obj.get("discountedPrice", "")
                cur = _detect_currency(base_str or disc_str)
                if cur in ("UAH", "unknown"):
                    bv = _parse_price_string(base_str)
                    dv = _parse_price_string(disc_str)
                    if dv > 0:
                        price_uah = dv
                        if bv > dv:
                            discount_pct = round((1 - dv / bv) * 100)
                    elif bv > 0:
                        price_uah = bv
        if price_uah <= 0:
            skus = raw.get("skus", [])
            if skus:
                pi = skus[0].get("price", {})
                if _detect_currency(pi.get("basePrice", "")) in ("UAH", "unknown"):
                    pv = pi.get("basePriceValue", 0)
                    if pv:
                        price_uah = float(pv)
        if price_uah <= 0:
            return None
        image_url = ""
        for m in raw.get("media", []):
            if m.get("role") in ("MASTER", "GAMEHUB_COVER_ART", "PORTRAIT_BANNER"):
                image_url = m.get("url", "")
                break
        if not image_url and raw.get("media"):
            image_url = raw["media"][0].get("url", "")
        original_id = raw.get("id", "") or ""
        concept = raw.get("concept", {}) or {}
        if not original_id:
            original_id = str(concept.get("id", ""))
        si = raw.get("storeInfo", {}) or {}
        release_date = si.get("releaseDate") or concept.get("releaseDate")
        platforms = raw.get("platforms", [])
        if platforms:
            platform = ", ".join(platforms)
        desc = raw.get("description", "") or ""
        if len(desc) > 500:
            desc = desc[:497] + "..."
        return {
            "title": name, "description": desc, "image_url": image_url,
            "price_uah": price_uah, "platform": platform, "rating": 0,
            "is_featured": 0, "discount_pct": discount_pct,
            "original_id": original_id, "release_date": release_date,
            "product_type": "game", "is_preorder": 0,
        }
    except Exception as e:
        log.error("Parse error: %s", e)
        return None

SUBSCRIPTIONS = [
    {"title": "PlayStation Plus Deluxe на 1 месяц (Турция)", "cat": "ps-plus", "price_byn": 55, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Deluxe на 3 месяца (Турция)", "cat": "ps-plus", "price_byn": 150, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Deluxe на 12 месяцев (Турция)", "cat": "ps-plus", "price_byn": 435, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Extra на 1 месяц (Турция)", "cat": "ps-plus", "price_byn": 55, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Extra на 3 месяца (Турция)", "cat": "ps-plus", "price_byn": 140, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Extra на 12 месяцев (Турция)", "cat": "ps-plus", "price_byn": 370, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Essential на 1 месяц (Турция)", "cat": "ps-plus", "price_byn": 55, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Essential на 3 месяца (Турция)", "cat": "ps-plus", "price_byn": 80, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Essential на 12 месяцев (Турция)", "cat": "ps-plus", "price_byn": 225, "platform": "PSN", "product_type": "subscription"},
    {"title": "EA Play на 1 месяц (Турция)", "cat": "ea-play", "price_byn": 35, "platform": "PSN", "product_type": "subscription"},
    {"title": "EA Play на 12 месяцев (Турция)", "cat": "ea-play", "price_byn": 150, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Люкс на 1 месяц (Украина)", "cat": "ps-plus", "price_byn": 60, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Люкс на 3 месяца (Украина)", "cat": "ps-plus", "price_byn": 130, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Люкс на 12 месяцев (Украина)", "cat": "ps-plus", "price_byn": 280, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Экстра на 1 месяц (Украина)", "cat": "ps-plus", "price_byn": 50, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Экстра на 3 месяца (Украина)", "cat": "ps-plus", "price_byn": 120, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Экстра на 12 месяцев (Украина)", "cat": "ps-plus", "price_byn": 260, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Основной на 1 месяц (Украина)", "cat": "ps-plus", "price_byn": 40, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Основной на 3 месяца (Украина)", "cat": "ps-plus", "price_byn": 80, "platform": "PSN", "product_type": "subscription"},
    {"title": "PlayStation Plus Основной на 12 месяцев (Украина)", "cat": "ps-plus", "price_byn": 160, "platform": "PSN", "product_type": "subscription"},
    {"title": "EA Play на 1 месяц (Украина)", "cat": "ea-play", "price_byn": 40, "platform": "PSN", "product_type": "subscription"},
    {"title": "EA Play на 12 месяцев (Украина)", "cat": "ea-play", "price_byn": 120, "platform": "PSN", "product_type": "subscription"},
]

TOPUP_CARDS = [
    {"title": "Пополнение PlayStation Store UA на 400 гривен", "cat": "gift-cards", "price_byn": 50, "platform": "PSN", "product_type": "topup"},
    {"title": "Пополнение PlayStation Store UA на 600 гривен", "cat": "gift-cards", "price_byn": 65, "platform": "PSN", "product_type": "topup"},
    {"title": "Пополнение PlayStation Store UA на 1000 гривен", "cat": "gift-cards", "price_byn": 100, "platform": "PSN", "product_type": "topup"},
    {"title": "Пополнение PlayStation Store UA на 2000 гривен", "cat": "gift-cards", "price_byn": 200, "platform": "PSN", "product_type": "topup"},
    {"title": "Пополнение PlayStation Store UA на 3000 гривен", "cat": "gift-cards", "price_byn": 300, "platform": "PSN", "product_type": "topup"},
    {"title": "Пополнение PlayStation Store UA на 4000 гривен", "cat": "gift-cards", "price_byn": 400, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 250 лир", "cat": "gift-cards", "price_byn": 35, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 500 лир", "cat": "gift-cards", "price_byn": 55, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 750 лир", "cat": "gift-cards", "price_byn": 80, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 1000 лир", "cat": "gift-cards", "price_byn": 105, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 1500 лир", "cat": "gift-cards", "price_byn": 150, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 2000 лир", "cat": "gift-cards", "price_byn": 190, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 2500 лир", "cat": "gift-cards", "price_byn": 240, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 3000 лир", "cat": "gift-cards", "price_byn": 290, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 4000 лир", "cat": "gift-cards", "price_byn": 380, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PlayStation Store TL на 5000 лир", "cat": "gift-cards", "price_byn": 450, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 50 злотых (Польша)", "cat": "gift-cards", "price_byn": 56, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 100 злотых (Польша)", "cat": "gift-cards", "price_byn": 113, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 200 злотых (Польша)", "cat": "gift-cards", "price_byn": 225, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 300 злотых (Польша)", "cat": "gift-cards", "price_byn": 338, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 350 злотых (Польша)", "cat": "gift-cards", "price_byn": 400, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 500 злотых (Польша)", "cat": "gift-cards", "price_byn": 560, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 650 злотых (Польша)", "cat": "gift-cards", "price_byn": 600, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 900 злотых (Польша)", "cat": "gift-cards", "price_byn": 850, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 1100 злотых (Польша)", "cat": "gift-cards", "price_byn": 990, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 1000 рупий (Индия)", "cat": "gift-cards", "price_byn": 60, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 2000 рупий (Индия)", "cat": "gift-cards", "price_byn": 120, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 3000 рупий (Индия)", "cat": "gift-cards", "price_byn": 180, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 4000 рупий (Индия)", "cat": "gift-cards", "price_byn": 240, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 5000 рупий (Индия)", "cat": "gift-cards", "price_byn": 265, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 6000 рупий (Индия)", "cat": "gift-cards", "price_byn": 315, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 7000 рупий (Индия)", "cat": "gift-cards", "price_byn": 360, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 8000 рупий (Индия)", "cat": "gift-cards", "price_byn": 410, "platform": "PSN", "product_type": "topup"},
    {"title": "Карта пополнения PSN на 9000 рупий (Индия)", "cat": "gift-cards", "price_byn": 455, "platform": "PSN", "product_type": "topup"},
]

CATEGORIES = [
    ("ps-games", "PS Games"),
    ("ps-plus", "PS Plus"),
    ("ea-play", "EA Play"),
    ("gift-cards", "Карты пополнения"),
    ("dlc", "DLC"),
    ("currency", "Игровая валюта"),
]

async def _build_concept_image_cache(client) -> dict:
    """Fetch the new-games category and extract name→image_url from ALL concepts,
    even those without a price. Returns {lowercase_name: image_url}."""
    cache = {}
    try:
        data = await _fetch_strand_page(client, NEW_GAMES_CATEGORY_ID, size=24, offset=0)
        sd = data.get("data", {}).get("categoryStrandRetrieve", {})
        concepts = sd.get("concepts") or []
        for c in concepts:
            name = c.get("name", "")
            if not name:
                continue
            # Try concept-level media first, then defaultProduct media
            media_list = c.get("media") or []
            dp = c.get("defaultProduct") or {}
            if not media_list:
                media_list = dp.get("media") or []
            img = ""
            for m in media_list:
                if m.get("role") in ("MASTER", "GAMEHUB_COVER_ART", "PORTRAIT_BANNER"):
                    img = m.get("url", "")
                    break
            if not img and media_list:
                img = media_list[0].get("url", "")
            if img:
                cache[name.lower()] = img
        log.info("Concept image cache: %d entries", len(cache))
    except Exception as e:
        log.warning("Concept image cache build failed: %s", e)
    return cache


async def _search_ps_image(client, search_term: str) -> str:
    """Search for a game's cover image via Steam store search + appdetails.
    Uses Steam storesearch to find appid, then appdetails to get the actual CDN URL."""
    try:
        steam_search = f"https://store.steampowered.com/api/storesearch/?term={search_term}&cc=us&l=en"
        r1 = await client.get(steam_search, headers={"User-Agent": "tg-shop/1.0"}, timeout=10)
        if r1.status_code == 200:
            items = r1.json().get("items", [])
            for item in items[:2]:
                app_id = item.get("id")
                if not app_id:
                    continue
                detail_url = f"https://store.steampowered.com/api/appdetails/?appids={app_id}&filters=basic"
                r2 = await client.get(detail_url, headers={"User-Agent": "tg-shop/1.0"}, timeout=10)
                if r2.status_code == 200:
                    info = r2.json().get(str(app_id), {}).get("data", {})
                    header = info.get("header_image", "")
                    if header:
                        log.info("Steam image found for '%s': appid=%s", search_term, app_id)
                        return header
    except Exception as e:
        log.warning("Steam search for '%s' failed: %s", search_term, e)
    return ""


async def _ensure_categories(db):
    for slug, name in CATEGORIES:
        await db.execute("INSERT OR IGNORE INTO categories (slug, name) VALUES (?, ?)", (slug, name))
    await db.commit()
    cat = {}
    async with db.execute("SELECT id, slug FROM categories") as cur:
        async for row in cur:
            cat[row[1]] = row[0]
    return cat

@router.get("/parse-debug-home")
async def parse_debug_home():
    """Explore PS Store homepage strands to find the new-releases section."""
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        headers = _build_headers()
        results = {}
        # PS Store homepage category IDs to find the new-releases strand
        home_cats = {
            "ps_store_home": "ac699f45-e984-4f0b-9a39-dbf8bff88cf4",
            "ps5_home":      "987124c4-cd79-4e29-a0be-76ecc8e3cad5",
            "new_releases_ua": "2e47bb6b-4fc5-45f8-94b0-e1a62dd58a4c",
            "whats_new":     "8d7c12a3-0f5e-4b82-a0c8-9e1d37f2b445",
        }
        for name, cid in home_cats.items():
            try:
                data = await _fetch_strand_page(client, cid, size=5, offset=0)
                sd = data.get("data", {}).get("categoryStrandRetrieve", {})
                strands = sd.get("strands", [])
                products, total = _products_from_strand_data(sd)
                priced = [p for p in products if _has_prices([p])]
                result = {"total": total, "strands": len(strands), "products": len(products), "priced": len(priced)}
                if strands:
                    result["strand_names"] = [s.get("reportingName","?")[:30] for s in strands[:5]]
                if products:
                    result["first"] = products[0].get("name","?")[:40]
                results[name] = result
            except Exception as e:
                results[name] = f"ERROR: {str(e)[:60]}"
        # Also try the new-games category (e1699f77) but with offset=5,10,24 to see if there are more pages
        for offset in [0, 5, 12, 24, 48]:
            try:
                data = await _fetch_strand_page(client, NEW_GAMES_CATEGORY_ID, size=24, offset=offset)
                sd = data.get("data", {}).get("categoryStrandRetrieve", {})
                concepts = sd.get("concepts", [])
                products, _ = _products_from_strand_data(sd)
                priced = [p for p in products if _has_prices([p])]
                results[f"new_games_offset={offset}"] = {
                    "concepts": len(concepts), "products": len(products), "priced": len(priced),
                    "names": [c.get("name","?")[:30] for c in concepts[:5]]
                }
            except Exception as e:
                results[f"new_games_offset={offset}"] = f"ERROR: {str(e)[:60]}"
    return results


@router.get("/parse-debug-new")
async def parse_debug_new():
    """Explore PS Store new releases via different approaches."""
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    results = {}
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        headers = _build_headers()
        # Approach 1: strand with sortBy on PS5 category
        for sv in ["RELEASE_DATE_DESC", "NEWLY_RELEASED", None]:
            try:
                variables = {"id": PS_CATEGORIES["ps5_games"], "pageArgs": {"size": 5, "offset": 0}}
                if sv:
                    variables["sortBy"] = sv
                extensions = {"persistedQuery": {"version": 1, "sha256Hash": STRAND_SHA256}}
                url = f"{PS_GRAPHQL}?operationName=categoryStrandRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
                resp = await client.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    sd = resp.json().get("data", {}).get("categoryStrandRetrieve", {})
                    products, _ = _products_from_strand_data(sd)
                    results[f"strand sortBy={sv}"] = {"count": len(products), "first": products[0].get("name","?")[:30] if products else "EMPTY"}
                else:
                    results[f"strand sortBy={sv}"] = f"HTTP {resp.status_code}"
            except Exception as e:
                results[f"strand sortBy={sv}"] = str(e)
        # Approach 2: try UA-specific new releases category IDs
        test_ids = {
            "new_ua_1": "b2d28af0-2fe6-4a0f-8540-a69c74c25e60",
            "new_ua_2": "2e47bb6b-2836-4fa4-b030-57a36f7826e3",
            "new_ua_3": "36902a9c-4a8a-4f35-a0fc-af8e5e0f5e64",
            "new_ua_4": "96a2ed9d-c296-4c1d-9ac6-fe01e6b36bd3",
        }
        for name, cid in test_ids.items():
            try:
                data = await _fetch_strand_page(client, cid, size=3, offset=0)
                sd = data.get("data", {}).get("categoryStrandRetrieve", {})
                products, total = _products_from_strand_data(sd)
                priced = [p for p in products if _has_prices([p])]
                results[f"cat {name}"] = {"total": total, "products": len(products), "priced": len(priced), "first": products[0].get("name","?")[:30] if products else "EMPTY"}
            except Exception as e:
                results[f"cat {name}"] = f"ERROR: {str(e)[:50]}"
        # Approach 3: look at what fields the grid default returns (name + storeInfo check)
        try:
            data = await _fetch_grid_page(client, PS_CATEGORIES["ps5_games"], size=3, offset=0)
            grid = data.get("data", {}).get("categoryGridRetrieve", {})
            products = grid.get("products", [])
            if products:
                p0 = products[0]
                results["grid_product_keys"] = list(p0.keys())
                results["grid_product_skus"] = (p0.get("skus") or [{}])[:1]
        except Exception as e:
            results["grid_check"] = str(e)
    return results


@router.get("/parse-debug-sort/{cat_id}")
async def parse_debug_sort(cat_id: str):
    """Test multiple sortBy values AND filterBy date filters on a category grid."""
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    results = {}
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        # Test 1: sortBy values
        for sv in ["RELEASE_DATE_DESC", "NEWLY_RELEASED", "TOP_SELLERS", "TITLE_ASC", None]:
            try:
                variables = {"id": cat_id, "pageArgs": {"size": 3, "offset": 0}, "sortBy": sv, "filterBy": [], "facetOptions": []}
                extensions = {"persistedQuery": {"version": 1, "sha256Hash": GRID_SHA256}}
                url = f"{PS_GRAPHQL}?operationName=categoryGridRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
                resp = await client.get(url, headers=_build_headers(), timeout=10)
                if resp.status_code != 200:
                    results[f"sort={sv}"] = f"HTTP {resp.status_code}"
                    continue
                grid = resp.json().get("data", {}).get("categoryGridRetrieve", {})
                products = grid.get("products", [])
                results[f"sort={sv}"] = {"count": len(products), "first": products[0].get("name","?")[:30] if products else "EMPTY"}
            except Exception as e:
                results[f"sort={sv}"] = str(e)
        # Test 2: filterBy date values
        for fv in ["LAST_7_DAYS", "LAST_30_DAYS", "LAST_90_DAYS", "LAST_MONTH", "NEW"]:
            try:
                variables = {"id": cat_id, "pageArgs": {"size": 5, "offset": 0}, "sortBy": None,
                             "filterBy": [{"name": "RELEASE_DATE", "values": [fv]}], "facetOptions": []}
                extensions = {"persistedQuery": {"version": 1, "sha256Hash": GRID_SHA256}}
                url = f"{PS_GRAPHQL}?operationName=categoryGridRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
                resp = await client.get(url, headers=_build_headers(), timeout=10)
                if resp.status_code != 200:
                    results[f"filter={fv}"] = f"HTTP {resp.status_code}"
                    continue
                grid = resp.json().get("data", {}).get("categoryGridRetrieve", {})
                products = grid.get("products", [])
                results[f"filter={fv}"] = {"count": len(products), "first": products[0].get("name","?")[:30] if products else "EMPTY"}
            except Exception as e:
                results[f"filter={fv}"] = str(e)
        # Test 3: facetOptions for release date
        try:
            variables = {"id": cat_id, "pageArgs": {"size": 5, "offset": 0}, "sortBy": None, "filterBy": [],
                         "facetOptions": [{"key": "RELEASE_DATE", "value": "LAST_30_DAYS"}]}
            extensions = {"persistedQuery": {"version": 1, "sha256Hash": GRID_SHA256}}
            url = f"{PS_GRAPHQL}?operationName=categoryGridRetrieve&variables={json.dumps(variables, separators=(',',':'))}&extensions={json.dumps(extensions, separators=(',',':'))}"
            resp = await client.get(url, headers=_build_headers(), timeout=10)
            if resp.status_code == 200:
                grid = resp.json().get("data", {}).get("categoryGridRetrieve", {})
                products = grid.get("products", [])
                results["facet=RELEASE_DATE/LAST_30_DAYS"] = {"count": len(products), "first": products[0].get("name","?")[:30] if products else "EMPTY"}
            else:
                results["facet=RELEASE_DATE/LAST_30_DAYS"] = f"HTTP {resp.status_code}"
        except Exception as e:
            results["facet=..."] = str(e)
    return results


@router.get("/parse-debug-cat/{cat_id}")
async def parse_debug_cat(cat_id: str):
    """Debug any category ID: shows raw keys and 3 sample products."""
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        try:
            data = await _fetch_strand_page(client, cat_id, size=5, offset=0)
            sd = data.get("data", {}).get("categoryStrandRetrieve", {})
            products, total = _products_from_strand_data(sd)
            sample = []
            for p in products[:3]:
                sample.append({
                    "name": p.get("name"),
                    "price": p.get("price"),
                    "webctas": (p.get("webctas") or [])[:1],
                    "platforms": p.get("platforms"),
                    "keys": list(p.keys()),
                })
            return {
                "raw_keys": list(sd.keys()),
                "products_direct": len(sd.get("products") or []),
                "strands": len(sd.get("strands") or []),
                "concepts": len(sd.get("concepts") or []),
                "total": total,
                "extracted": len(products),
                "sample": sample,
            }
        except Exception as e:
            return {"error": str(e)}

@router.get("/parse-debug")
async def parse_debug():
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        errors = {}
        # Try strand
        try:
            data = await _fetch_strand_page(client, PS_CATEGORIES["ps5_games"], size=3, offset=0)
            strand_data = data.get("data", {}).get("categoryStrandRetrieve", {})
            products = strand_data.get("products", [])
            strands = strand_data.get("strands", [])
            sample = []
            # Direct products
            for p in products[:3]:
                sample.append({"name": p.get("name"), "price": p.get("price"), "webctas": p.get("webctas", [])[:1], "platforms": p.get("platforms")})
            # From strands
            for strand in strands[:2]:
                for p in strand.get("products", [])[:2]:
                    sample.append({"name": p.get("name"), "price": p.get("price"), "webctas": p.get("webctas", [])[:1], "platforms": p.get("platforms")})
            return {
                "method": "categoryStrandRetrieve",
                "products_count": len(products),
                "strands_count": len(strands),
                "total": strand_data.get("pageInfo", {}).get("totalCount", 0),
                "sample_products": sample,
                "raw_keys": list(strand_data.keys()),
            }
        except Exception as e:
            errors["strand"] = str(e)
        # Try grid
        try:
            data = await _fetch_grid_page(client, PS_CATEGORIES["ps5_games"], size=3, offset=0)
            grid = data.get("data", {}).get("categoryGridRetrieve", {})
            products = grid.get("products", [])[:2]
            sample = [{"name": p.get("name"), "webctas": p.get("webctas", [])[:1]} for p in products]
            return {"method": "categoryGridRetrieve", "errors": errors, "product_count": len(grid.get("products", [])), "sample_products": sample}
        except Exception as e2:
            errors["grid"] = str(e2)
        return {"errors": errors}

@router.get("/my-ip")
async def my_ip():
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        resp = await client.get("https://httpbin.org/ip", timeout=10)
        return {"proxy_configured": bool(proxy), "result": resp.json()}

@router.post("/parse")
async def parse_ps_store(db=Depends(get_db)):
    cat_map = await _ensure_categories(db)
    await db.execute("PRAGMA foreign_keys = OFF")
    await db.execute("DELETE FROM products")
    await db.execute("PRAGMA foreign_keys = ON")
    await db.commit()
    stats = {"games": 0, "deals_fetched": 0, "deals_by_id": 0, "deals_by_title": 0, "deals_inserted": 0, "top10_updated": 0, "top10_inserted": 0, "new_games": 0, "preorders": 0, "tr_prices": 0, "subscriptions": 0, "topup_cards": 0, "errors": 0}
    from datetime import date, timedelta
    today = date.today().isoformat()
    proxy = _get_proxy()
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        for pk, cid in PS_CATEGORIES.items():
            plat = "PS5" if "ps5" in pk else "PS4"
            log.info("Fetching %s games...", plat)
            try:
                raws = await _fetch_all_games(client, cid, max_pages=30)
                log.info("Got %d raw %s products", len(raws), plat)
                for raw in raws:
                    parsed = _parse_ps_product(raw, plat)
                    if not parsed:
                        stats["errors"] += 1
                        continue
                    try:
                        await db.execute(
                            """INSERT OR REPLACE INTO products (category_id, title, description, image_url, price_uah, platform, rating, is_featured, is_active, discount_pct, original_id, release_date, product_type, is_preorder) VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?)""",
                            (cat_map.get("ps-games", 1), parsed["title"], parsed["description"], parsed["image_url"], parsed["price_uah"], parsed["platform"], parsed["rating"], parsed["is_featured"], parsed["discount_pct"], parsed["original_id"], parsed["release_date"], parsed["product_type"], parsed["is_preorder"]))
                        stats["games"] += 1
                    except Exception as e:
                        log.error("Insert fail %s: %s", parsed["title"], e)
                        stats["errors"] += 1
            except Exception as e:
                log.error("Fetch %s fail: %s", plat, e)
                stats["errors"] += 1

        # Parse deals category: try match by original_id → title → insert as new
        log.info("Fetching PS Store deals (ID: %s)...", DEALS_CATEGORY_ID)
        try:
            deal_raws = await _fetch_all_games(client, DEALS_CATEGORY_ID, max_pages=30)
            stats["deals_fetched"] = len(deal_raws)
            log.info("Deals fetched: %d total", len(deal_raws))
            for raw in deal_raws:
                parsed = _parse_ps_product(raw, "PS5/PS4")
                if not parsed or parsed["discount_pct"] <= 0:
                    continue
                try:
                    matched = False
                    # 1) Match by original_id
                    if parsed["original_id"]:
                        cur = await db.execute(
                            "UPDATE products SET discount_pct = ?, price_uah = ? WHERE original_id = ?",
                            (parsed["discount_pct"], parsed["price_uah"], parsed["original_id"]),
                        )
                        if cur.rowcount > 0:
                            stats["deals_by_id"] += 1
                            matched = True
                    # 2) Match by title (case-insensitive) if id didn't match
                    if not matched and parsed["title"]:
                        cur = await db.execute(
                            "UPDATE products SET discount_pct = ?, price_uah = ? WHERE LOWER(title) = LOWER(?)",
                            (parsed["discount_pct"], parsed["price_uah"], parsed["title"]),
                        )
                        if cur.rowcount > 0:
                            stats["deals_by_title"] += 1
                            matched = True
                    # 3) Insert as new record if not found
                    if not matched:
                        await db.execute(
                            """INSERT OR IGNORE INTO products
                               (category_id, title, description, image_url, price_uah, platform,
                                rating, is_featured, is_active, discount_pct, original_id,
                                release_date, product_type, is_preorder)
                               VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?)""",
                            (cat_map.get("ps-games", 1), parsed["title"], parsed["description"],
                             parsed["image_url"], parsed["price_uah"], parsed["platform"],
                             parsed["rating"], parsed["is_featured"], parsed["discount_pct"],
                             parsed["original_id"], parsed["release_date"],
                             parsed["product_type"], parsed["is_preorder"]),
                        )
                        stats["deals_inserted"] += 1
                except Exception as e:
                    log.error("Deal fail %s: %s", parsed.get("original_id"), e)
                    stats["errors"] += 1
            log.info(
                "Deals result: fetched=%d by_id=%d by_title=%d inserted=%d",
                stats["deals_fetched"], stats["deals_by_id"],
                stats["deals_by_title"], stats["deals_inserted"],
            )
        except Exception as e:
            log.error("Deals fetch fail: %s", e)
            stats["errors"] += 1

        # ── TOP-10 curated games ──────────────────────────────────────────
        log.info("Applying TOP-10 curated games (building concept image cache)...")
        concept_imgs = await _build_concept_image_cache(client)

        for i, entry in enumerate(TOP_10_GAMES):
            kw = entry["keyword"]
            like_pat = entry.get("like_pattern") or f"%{kw}%"
            try:
                fallback_try = entry.get("price_try") or 0
                cur = await db.execute(
                    """UPDATE products
                       SET rating = ?, is_featured = 1,
                           price_uah = ?, discount_pct = ?, is_preorder = ?,
                           price_try = COALESCE(NULLIF(price_try, 0), ?)
                       WHERE title LIKE ?""",
                    (entry["rating"], entry["price_uah"],
                     entry["discount_pct"], entry["is_preorder"],
                     fallback_try if fallback_try > 0 else None, like_pat),
                )
                if cur.rowcount > 0:
                    stats["top10_updated"] += 1
                    log.info("TOP10 updated %d row(s) for '%s'", cur.rowcount, kw)
                    # If the matched record has no image, patch it from concept cache
                    img = concept_imgs.get(kw.lower())
                    if not img:
                        # Also check entry-level hardcoded image
                        img = entry.get("image_url", "")
                    if img:
                        await db.execute(
                            "UPDATE products SET image_url = ? WHERE title LIKE ? AND (image_url IS NULL OR image_url = '')",
                            (img, like_pat),
                        )
                else:
                    # Not in DB — look up image in concept cache (fuzzy)
                    img = concept_imgs.get(kw.lower(), "")
                    if not img:
                        # Try partial match in cache
                        kw_lower = kw.lower()
                        for cname, curl in concept_imgs.items():
                            if kw_lower in cname or cname in kw_lower:
                                img = curl
                                break
                    # If still no image, try PS Store search globally
                    if not img and entry.get("search_term"):
                        img = await _search_ps_image(client, entry["search_term"])
                        if img:
                            log.info("TOP10 '%s': found image via PS search", kw)
                        else:
                            log.warning("TOP10 '%s': no image found anywhere", kw)
                    # Hardcoded fallback from entry itself
                    if not img:
                        img = entry.get("image_url", "")
                    await db.execute(
                        """INSERT OR REPLACE INTO products
                           (category_id, title, description, image_url, price_uah, price_try, platform,
                            rating, is_featured, is_active, discount_pct, original_id,
                            release_date, product_type, is_preorder)
                           VALUES (?,?,?,?,?,?,?,?,1,1,?,?,?,?,?)""",
                        (cat_map.get("ps-games", 1), kw, "", img,
                         entry["price_uah"], entry.get("price_try") or None, "PS5/PS4",
                         entry["rating"], entry["discount_pct"],
                         f"TOP10_{i:02d}", None, "game", entry["is_preorder"]),
                    )
                    stats["top10_inserted"] += 1
                    log.info("TOP10 inserted '%s' img=%s", kw, "yes" if img else "no")
            except Exception as e:
                log.error("TOP10 fail '%s': %s", kw, e)
                stats["errors"] += 1
        log.info("TOP-10 done: updated=%d inserted=%d",
                 stats["top10_updated"], stats["top10_inserted"])

        # ── Mark new games from PS Store "New Games" category ────────────
        # Runs AFTER TOP-10 so that TOP-10-inserted games (Crimson Desert etc.)
        # are already in the DB when the UPDATE runs.
        # Position-based dating: first 30 → release_date=today, rest → yesterday.
        # Position-based rating: first 10 → 4.0..3.1 (so they rank above others
        # in "Все игры" but below TOP-10 curated games).
        log.info("Marking new releases from PS Store New Games category...")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        try:
            seen_names: list = []        # ordered list of unique names
            seen_set: set = set()
            offset = 0
            while offset <= 240:
                data_ng = await _fetch_strand_page(client, NEW_GAMES_CATEGORY_ID, size=24, offset=offset)
                sd_ng = data_ng.get("data", {}).get("categoryStrandRetrieve", {})
                concepts_ng = sd_ng.get("concepts", [])
                if not concepts_ng:
                    break
                for c in concepts_ng:
                    name = c.get("name", "")
                    if not name or name in seen_set:
                        continue
                    seen_set.add(name)
                    seen_names.append(name)
                total_ng = sd_ng.get("pageInfo", {}).get("totalCount", 0)
                offset += 24
                if offset >= total_ng:
                    break

            marked = 0
            for rank, name in enumerate(seen_names):
                rdate = today if rank < 30 else yesterday
                # Rating boost for first 10: 4.0, 3.9, ..., 3.1
                new_rating = round(4.0 - rank * 0.1, 1) if rank < 10 else None

                if new_rating is not None:
                    rating_set = ", rating = ?"
                    rating_val = (new_rating,)
                else:
                    rating_set = ""
                    rating_val = ()

                # Exact title match
                hit = await db.execute(
                    f"UPDATE products SET release_date = ?{rating_set} WHERE LOWER(title) = LOWER(?) AND product_type = 'game'",
                    (rdate,) + rating_val + (name,),
                )
                if hit.rowcount > 0:
                    marked += hit.rowcount
                    continue
                # Prefix match (first 25 chars) — only when release_date is NULL to avoid overwriting today→yesterday
                if len(name) > 8:
                    hit2 = await db.execute(
                        f"UPDATE products SET release_date = ?{rating_set} WHERE LOWER(title) LIKE LOWER(?) AND product_type = 'game' AND release_date IS NULL",
                        (rdate,) + rating_val + (f"{name[:25]}%",),
                    )
                    if hit2.rowcount > 0:
                        marked += hit2.rowcount

            await db.commit()
            stats["new_games"] = marked
            log.info("New releases marked: %d (from %d unique concept names, top30=today top10=rated)", marked, len(seen_names))
        except Exception as e:
            log.warning("Mark new releases failed: %s", e)

        # ── New games (release_date=today for all priced items) ───────────
        log.info("Fetching new games (ID: %s)...", NEW_GAMES_CATEGORY_ID)
        try:
            new_raws = await _fetch_all_games(client, NEW_GAMES_CATEGORY_ID, max_pages=30)
            log.info("New games fetched: %d raw", len(new_raws))
            for raw in new_raws:
                parsed = _parse_ps_product(raw, "PS5/PS4")
                if not parsed:
                    continue  # no price — silently skip
                parsed["release_date"] = today
                try:
                    # INSERT OR IGNORE preserves price_try if row already exists
                    await db.execute(
                        """INSERT OR IGNORE INTO products
                           (category_id, title, description, image_url, price_uah, platform,
                            rating, is_featured, is_active, discount_pct, original_id,
                            release_date, product_type, is_preorder)
                           VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?)""",
                        (cat_map.get("ps-games", 1), parsed["title"], parsed["description"],
                         parsed["image_url"], parsed["price_uah"], parsed["platform"],
                         parsed["rating"], parsed["is_featured"], parsed["discount_pct"],
                         parsed["original_id"], parsed["release_date"],
                         parsed["product_type"], parsed["is_preorder"]),
                    )
                    await db.execute(
                        """UPDATE products SET
                               title=?, description=?, image_url=?, price_uah=?,
                               platform=?, discount_pct=?, release_date=?, is_active=1
                           WHERE original_id=?""",
                        (parsed["title"], parsed["description"], parsed["image_url"],
                         parsed["price_uah"], parsed["platform"], parsed["discount_pct"],
                         parsed["release_date"], parsed["original_id"]),
                    )
                    stats["new_games"] += 1
                except Exception as e:
                    log.error("New game insert fail %s: %s", parsed["title"], e)
                    stats["errors"] += 1
        except Exception as e:
            log.error("New games fetch fail: %s", e)
            stats["errors"] += 1

        # ── Preorders (is_preorder=1) ─────────────────────────────────────
        log.info("Fetching preorders (ID: %s)...", PREORDERS_CATEGORY_ID)
        try:
            pre_raws = await _fetch_all_games(client, PREORDERS_CATEGORY_ID, max_pages=30)
            log.info("Preorders fetched: %d raw", len(pre_raws))
            for raw in pre_raws:
                parsed = _parse_ps_product(raw, "PS5/PS4")
                if not parsed:
                    continue  # no price — silently skip
                parsed["is_preorder"] = 1
                try:
                    # INSERT OR IGNORE preserves price_try if row already exists
                    await db.execute(
                        """INSERT OR IGNORE INTO products
                           (category_id, title, description, image_url, price_uah, platform,
                            rating, is_featured, is_active, discount_pct, original_id,
                            release_date, product_type, is_preorder)
                           VALUES (?,?,?,?,?,?,?,?,1,?,?,?,?,?)""",
                        (cat_map.get("ps-games", 1), parsed["title"], parsed["description"],
                         parsed["image_url"], parsed["price_uah"], parsed["platform"],
                         parsed["rating"], parsed["is_featured"], parsed["discount_pct"],
                         parsed["original_id"], parsed["release_date"],
                         parsed["product_type"], parsed["is_preorder"]),
                    )
                    await db.execute(
                        """UPDATE products SET
                               title=?, description=?, image_url=?, price_uah=?,
                               platform=?, discount_pct=?, is_preorder=1, is_active=1
                           WHERE original_id=?""",
                        (parsed["title"], parsed["description"], parsed["image_url"],
                         parsed["price_uah"], parsed["platform"], parsed["discount_pct"],
                         parsed["original_id"]),
                    )
                    stats["preorders"] += 1
                except Exception as e:
                    log.error("Preorder insert fail %s: %s", parsed["title"], e)
                    stats["errors"] += 1
        except Exception as e:
            log.error("Preorders fetch fail: %s", e)
            stats["errors"] += 1

        # ── TR price pass ──────────────────────────────────────────────────
        # Fetch same categories with TR headers, update price_try.
        # Strategy: 1) match by original_id (exact), 2) fallback by title (LIKE).
        log.info("Starting TR price pass...")
        tr_cats = {**PS_CATEGORIES, "deals": DEALS_CATEGORY_ID,
                   "new_games": NEW_GAMES_CATEGORY_ID, "preorders": PREORDERS_CATEGORY_ID}
        for pk, cid in tr_cats.items():
            try:
                tr_raws = await _fetch_all_games(client, cid, max_pages=30, country="TR")
                log.info("TR %s: %d products", pk, len(tr_raws))
                for raw in tr_raws:
                    price_try = _parse_price_try(raw)
                    if price_try <= 0:
                        continue
                    product_id  = raw.get("id", "") or ""
                    concept_obj = raw.get("concept") or {}
                    concept_id  = str(concept_obj.get("id", "")) if concept_obj.get("id") else ""
                    name = raw.get("name", "")

                    matched = False
                    # 1) Exact product-SKU match
                    if product_id:
                        cur = await db.execute(
                            "UPDATE products SET price_try = ? WHERE original_id = ?",
                            (price_try, product_id),
                        )
                        if cur.rowcount > 0:
                            stats["tr_prices"] += cur.rowcount
                            matched = True

                    # 2) Concept-ID match — same concept, different regional SKU
                    #    (UA stored concept.id as original_id when no product SKU was found)
                    if not matched and concept_id and concept_id != product_id:
                        cur = await db.execute(
                            "UPDATE products SET price_try = ? WHERE original_id = ? AND product_type = 'game'",
                            (price_try, concept_id),
                        )
                        if cur.rowcount > 0:
                            stats["tr_prices"] += cur.rowcount
                            matched = True

                    # 3) Exact title match
                    if not matched and name:
                        cur = await db.execute(
                            "UPDATE products SET price_try = ? WHERE LOWER(title) = LOWER(?) AND product_type = 'game'",
                            (price_try, name),
                        )
                        if cur.rowcount > 0:
                            stats["tr_prices"] += cur.rowcount
                            matched = True

                    # 4) Prefix title match for long names (first 30 chars)
                    if not matched and name and len(name) > 10:
                        cur = await db.execute(
                            "UPDATE products SET price_try = ? WHERE LOWER(title) LIKE LOWER(?) AND product_type = 'game' AND price_try IS NULL",
                            (price_try, f"{name[:30]}%"),
                        )
                        if cur.rowcount > 0:
                            stats["tr_prices"] += cur.rowcount

            except Exception as e:
                log.warning("TR pass for %s failed: %s", pk, e)
        await db.commit()
        log.info("TR prices updated: %d", stats["tr_prices"])

        # ── Targeted TR price lookup for TOP_10 games still missing price_try ──
        # The main TR pass matches by original_id/title from category pages.
        # Games that were top10_inserted (not found in main UA parse) may have
        # original_id="TOP10_XX" which never matches in TR. This step fetches
        # all TR categories once more and does LIKE-pattern matching specifically
        # for TOP_10 games that still have price_try = NULL.
        missing = []
        for entry in TOP_10_GAMES:
            like_pat = entry.get("like_pattern") or f"%{entry['keyword']}%"
            cur = await db.execute(
                "SELECT id, price_try FROM products WHERE title LIKE ? AND product_type='game'",
                (like_pat,),
            )
            row = await cur.fetchone()
            if row and row[1] is None:
                missing.append(entry)
        if missing:
            log.info("TOP10 targeted TR lookup: %d games still missing price_try", len(missing))
            tr_lookup_cats = {**PS_CATEGORIES,
                              "deals":     DEALS_CATEGORY_ID,
                              "new_games": NEW_GAMES_CATEGORY_ID,
                              "preorders": PREORDERS_CATEGORY_ID}
            for pk, cid in tr_lookup_cats.items():
                if not missing:
                    break
                try:
                    tr_raws = await _fetch_all_games(client, cid, max_pages=30, country="TR")
                    for raw in tr_raws:
                        price_try = _parse_price_try(raw)
                        if price_try <= 0:
                            continue
                        tr_name = (raw.get("name") or "").strip()
                        if not tr_name:
                            continue
                        tr_name_l = tr_name.lower()
                        for entry in list(missing):
                            kw_l = entry["keyword"].lower()
                            like_pat = entry.get("like_pattern") or f"%{entry['keyword']}%"
                            # Match: TR title contains our keyword OR our keyword contains TR title
                            if kw_l in tr_name_l or tr_name_l in kw_l:
                                cur = await db.execute(
                                    "UPDATE products SET price_try = ? WHERE title LIKE ? AND product_type='game' AND price_try IS NULL",
                                    (price_try, like_pat),
                                )
                                if cur.rowcount > 0:
                                    stats["tr_prices"] += cur.rowcount
                                    missing.remove(entry)
                                    log.info("TOP10 TR found '%s' → price_try=%.0f (matched '%s' in %s)",
                                             entry["keyword"], price_try, tr_name, pk)
                                    break
                except Exception as e:
                    log.warning("TOP10 TR lookup for cat %s failed: %s", pk, e)
            await db.commit()
            if missing:
                log.warning("TOP10 TR lookup: still missing price_try for: %s",
                            [e["keyword"] for e in missing])
        else:
            log.info("TOP10 targeted TR lookup: all games already have price_try ✓")

    for i, sub in enumerate(SUBSCRIPTIONS):
        try:
            await db.execute("""INSERT OR REPLACE INTO products (category_id, title, description, image_url, price_uah, platform, rating, is_featured, is_active, discount_pct, original_id, product_type) VALUES (?,?,?,?,?,?,0,0,1,0,?,?)""",
                (cat_map.get(sub["cat"], 1), sub["title"], sub["title"], "", sub["price_byn"], sub["platform"], f"SUB_{i:03d}", sub["product_type"]))
            stats["subscriptions"] += 1
        except Exception as e:
            log.error("Sub fail: %s", e)
            stats["errors"] += 1

    for i, card in enumerate(TOPUP_CARDS):
        try:
            await db.execute("""INSERT OR REPLACE INTO products (category_id, title, description, image_url, price_uah, platform, rating, is_featured, is_active, discount_pct, original_id, product_type) VALUES (?,?,?,?,?,?,0,0,1,0,?,?)""",
                (cat_map.get(card["cat"], 1), card["title"], card["title"], "", card["price_byn"], card["platform"], f"CARD_{i:03d}", card["product_type"]))
            stats["topup_cards"] += 1
        except Exception as e:
            log.error("Card fail: %s", e)
            stats["errors"] += 1

    await db.commit()
    return {
        "status": "parsed",
        "games_added": stats["games"],
        "deals_fetched": stats["deals_fetched"],
        "deals_by_id": stats["deals_by_id"],
        "deals_by_title": stats["deals_by_title"],
        "deals_inserted": stats["deals_inserted"],
        "top10_updated": stats["top10_updated"],
        "top10_inserted": stats["top10_inserted"],
        "new_games_added": stats["new_games"],
        "preorders_added": stats["preorders"],
        "tr_prices_updated": stats["tr_prices"],
        "subscriptions_added": stats["subscriptions"],
        "topup_cards_added": stats["topup_cards"],
        "errors": stats["errors"],
    }


# ── Fetch Editions endpoint (SSE) ─────────────────────────────────────────────

import hashlib as _hashlib

def _check_admin_token(x_admin_token: Optional[str] = Header(None)) -> None:
    expected = _hashlib.sha256(settings.ADMIN_PASSWORD.encode()).hexdigest()
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


_editions_task: asyncio.Task | None = None
_editions_progress: dict = {}  # {"region": str, "done": int, "total": int, "started": str}


@router.get("/fetch-editions/status")
async def editions_status(
    _: None = Depends(_check_admin_token),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return editions task status + DB progress counts."""
    running = bool(_editions_task and not _editions_task.done())
    result = {"running": running}
    for region in ("UA", "TR"):
        async with db.execute(
            "SELECT COUNT(*) FROM products WHERE region=? AND is_active=1 AND product_type='game'",
            (region,),
        ) as cur:
            total = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM products WHERE region=? AND is_active=1 AND product_type='game' AND has_editions=1",
            (region,),
        ) as cur:
            with_editions = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM game_editions WHERE region=?", (region,)
        ) as cur:
            edition_rows = (await cur.fetchone())[0]
        result[region] = {
            "total_games": total,
            "with_editions": with_editions,
            "edition_rows": edition_rows,
            "pending": total - with_editions,
        }
    return result


@router.post("/fetch-editions/{region}")
async def run_fetch_editions(
    region: str,
    _: None = Depends(_check_admin_token),
):
    """Fetch game editions from PS Store product pages (SSE stream)."""
    global _editions_task

    region = region.upper()
    if region not in ("UA", "TR", "ALL"):
        raise HTTPException(status_code=400, detail=f"Unknown region: {region}")
    if _editions_task and not _editions_task.done():
        raise HTTPException(status_code=409, detail="Задача уже запущена")

    async def event_generator():
        global _editions_task
        from parser.tasks.fetch_editions import fetch_editions_task

        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def producer():
            try:
                async for line in fetch_editions_task(region):
                    await queue.put(line)
            except Exception as e:
                await queue.put(f"❌ Необработанная ошибка: {e}")
            finally:
                await queue.put(None)

        _editions_task = asyncio.create_task(producer())
        yield {"event": "start", "data": f"▶ Загрузка эдишенов {region}"}
        while True:
            line = await queue.get()
            if line is None:
                break
            yield {"event": "message", "data": line}
        yield {"event": "done", "data": "✅ Задача завершена"}

    return EventSourceResponse(event_generator())


# ── Parse All Games (UA + TR) endpoints ──────────────────────────────────────

_parse_games_task: asyncio.Task | None = None


def _sse_task(label: str, coro_factory):
    """Generic SSE wrapper for an async-generator task."""
    async def event_generator():
        global _parse_games_task
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def producer():
            try:
                async for line in coro_factory():
                    await queue.put(line)
            except Exception as e:
                await queue.put(f"❌ Необработанная ошибка: {e}")
            finally:
                await queue.put(None)

        _parse_games_task = asyncio.create_task(producer())
        yield {"event": "start", "data": f"▶ {label}"}
        while True:
            line = await queue.get()
            if line is None:
                break
            yield {"event": "message", "data": line}
        yield {"event": "done", "data": "✅ Задача завершена"}

    return EventSourceResponse(event_generator())


@router.post("/parse-games/ua")
async def run_parse_games_ua(_: None = Depends(_check_admin_token)):
    """Parse ALL PS5+PS4 games from Ukrainian PS Store (SSE stream)."""
    global _parse_games_task
    if _parse_games_task and not _parse_games_task.done():
        raise HTTPException(status_code=409, detail="Задача уже запущена")

    from parser.tasks.parse_games import run
    return _sse_task("Парсинг всех игр UA", run)


@router.post("/parse-games/tr")
async def run_parse_games_tr(_: None = Depends(_check_admin_token)):
    """Parse ALL PS5+PS4 games from Turkish PS Store (SSE stream)."""
    global _parse_games_task
    if _parse_games_task and not _parse_games_task.done():
        raise HTTPException(status_code=409, detail="Задача уже запущена")

    from parser.tasks.parse_games_tr import run
    return _sse_task("Парсинг всех игр TR", run)

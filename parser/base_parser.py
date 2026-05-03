"""
BaseParser — PS Store GraphQL client + DB helpers + product/edition parsing.

Constructor:
    BaseParser(region=None, db_path=None, log_callback=None)

    region       — overrides class-level self.region if given
    db_path      — path to shop.db (defaults to config.DB_PATH)
    log_callback — callable(str) for real-time log streaming

All region-specific parsers inherit from this class and set:
    country = "XX"   # PS Store country code
    region  = "XX"   # internal region label
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

import aiosqlite
import httpx

from parser.config import (
    PS_GRAPHQL, STRAND_SHA256, GRID_SHA256, PROXY_URL, DB_PATH,
    get_price_settings, calc_price_byn,
)

log = logging.getLogger(__name__)


# ── Price string helpers ──────────────────────────────────────────────────────

def parse_price_string(p: str | None) -> float:
    if not p:
        return 0.0
    s = (
        str(p)
        .replace("\xa0", "").replace("\u200b", "").replace(" ", "")
        .replace("₴", "").replace("₺", "")
        .replace("£", "").replace("$", "")
        .replace("€", "").replace(",", ".")
        .strip()
    )
    if s.lower() in ("free", "бесплатно", "безкоштовно", ""):
        return 0.0
    s = re.sub(r"[^\d.]", "", s)
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def detect_currency(price_str: str | None) -> str:
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


# ── Platform normaliser ───────────────────────────────────────────────────────

_PS5_RE  = re.compile(r'\bPS[\s\-]?5\b', re.I)
_PS4_RE  = re.compile(r'\bPS[\s\-]?4\b', re.I)
_VR2_RE  = re.compile(r'\bPS[\s\-]?VR[\s\-]?2\b', re.I)


def normalize_platform(platforms) -> str | None:
    """
    Return a canonical platform string from the PS Store `platforms` field.

    Input: list  → ["PS5", "PS4"] / ["PS4 & PS5"] / ["PSVR2"]
           str   → "PS5/PS4" / "PS4™" / "PS"
           None  → None

    Output: "PS5" | "PS4" | "PS4, PS5" | "PS VR2" | None
    """
    if not platforms:
        return None
    raw = " ".join(str(p) for p in platforms) if isinstance(platforms, list) else str(platforms)
    if _VR2_RE.search(raw):
        return "PS VR2"
    has5 = bool(_PS5_RE.search(raw))
    has4 = bool(_PS4_RE.search(raw))
    if has5 and has4:
        return "PS4, PS5"
    if has5:
        return "PS5"
    if has4:
        return "PS4"
    return None


# ── Release date normaliser ───────────────────────────────────────────────────

_ISO_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')

_DATE_FMTS = [
    '%Y-%m-%d',   # ISO — check first
    '%d.%m.%Y',   # DD.MM.YYYY  (UA / TR locale)
    '%d/%m/%Y',   # DD/MM/YYYY
    '%m/%d/%Y',   # MM/DD/YYYY  (US)
    '%B %d, %Y',  # "January 01, 2024"
    '%b %d, %Y',  # "Jan 01, 2024"
]


def parse_release_date(date_val) -> str | None:
    """
    Parse any date string returned by the PS Store API into ISO YYYY-MM-DD.
    Returns None if the value is missing or unrecognisable.
    """
    if not date_val:
        return None
    s = str(date_val).strip()
    # Fast path: already ISO (may have time part)
    if _ISO_RE.match(s):
        return s[:10]
    for fmt in _DATE_FMTS[1:]:  # skip ISO — already handled above
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


# ── Product validator ─────────────────────────────────────────────────────────

_ALLOWED_PLATFORMS = {"PS5", "PS4", "PS4, PS5", "PS VR2", None}


def validate_product(product: dict) -> dict:
    """
    Sanitise a parsed product dict before saving to DB.
    - Normalises platform to one of the canonical values (or None)
    - Ensures release_date is ISO YYYY-MM-DD or None
    """
    # Platform
    raw_plat = product.get("platform")
    if raw_plat not in _ALLOWED_PLATFORMS:
        product["platform"] = normalize_platform(raw_plat)

    # Release date
    raw_date = product.get("release_date")
    if raw_date is not None:
        product["release_date"] = parse_release_date(raw_date)

    return product


# ── Main parser class ─────────────────────────────────────────────────────────

class BaseParser:
    """Shared PS Store API client + DB/logging infrastructure."""

    country: str = "UA"   # PS Store country code
    region:  str = "UA"   # our internal region label

    def __init__(
        self,
        region: str | None = None,
        db_path: "Path | str | None" = None,
        log_callback: "Callable[[str], None] | None" = None,
    ) -> None:
        if region is not None:
            self.region = region

        self._db_path: Path = Path(db_path) if db_path else DB_PATH
        self._log_callback = log_callback

        proxy = PROXY_URL or None
        transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
        self.client = httpx.AsyncClient(transport=transport, follow_redirects=True)

    async def __aenter__(self) -> "BaseParser":
        return self

    async def __aexit__(self, *_) -> None:
        await self.client.aclose()

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        """Send log message to the callback and Python logger."""
        if self._log_callback:
            self._log_callback(msg)
        log.info(msg)

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self, operation_name: str = "") -> dict:
        """JSON/GraphQL headers for PS Store API."""
        locale = "tr-TR" if self.country == "TR" else "ru-UA"
        h = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Content-Type": "application/json",
            "Origin": "https://store.playstation.com",
            "Referer": "https://store.playstation.com/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Apollographql-Client-Name": "@sie-ppr-web-store/app",
            "Apollographql-Client-Version": "0.109.0",
            "X-Psn-App-Ver": "@sie-ppr-web-store/app/0.109.0-",
            "X-Psn-Store-Locale-Override": locale,
            "X-Psn-Correlation-Id": str(uuid.uuid4()),
            "X-Psn-Request-Id": str(uuid.uuid4()),
            "Cookie": f"countryCode={self.country}",
            # Required to bypass Apollo CSRF protection on GET requests
            "apollo-require-preflight": "true",
        }
        if operation_name:
            h["x-apollo-operation-name"] = operation_name
        return h

    def _page_headers(self) -> dict:
        """Browser-like headers for regular page requests."""
        locale = "tr-TR" if self.country == "TR" else "ru-UA"
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": f"{locale},en-US;q=0.7,en;q=0.5",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "Cookie": f"countryCode={self.country}",
        }

    async def get_page(self, url: str) -> str:
        """
        Fetch a URL and return response text.
        Retries up to 3 times with a 2-second delay.
        Returns empty string if all attempts fail.
        """
        for attempt in range(3):
            try:
                resp = await self.client.get(
                    url, headers=self._page_headers(), timeout=30
                )
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt < 2:
                    self._log(f"⚠️ get_page попытка {attempt + 1} неудачна: {e}, повтор...")
                    await asyncio.sleep(2)
                else:
                    self._log(f"❌ get_page не удалось после 3 попыток: {url} — {e}")
        return ""

    # ── GraphQL fetchers ──────────────────────────────────────────────────────

    async def fetch_strand_page(
        self, category_id: str, size: int = 24, offset: int = 0
    ) -> dict:
        variables = {"id": category_id, "pageArgs": {"size": size, "offset": offset}}
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": STRAND_SHA256}}
        url = (
            f"{PS_GRAPHQL}?operationName=categoryStrandRetrieve"
            f"&variables={json.dumps(variables, separators=(',', ':'))}"
            f"&extensions={json.dumps(extensions, separators=(',', ':'))}"
        )
        resp = await self.client.get(
            url, headers=self._headers("categoryStrandRetrieve"), timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_grid_page(
        self, category_id: str, size: int = 24, offset: int = 0
    ) -> dict:
        variables = {
            "id": category_id,
            "pageArgs": {"size": size, "offset": offset},
            "sortBy": None,
            "filterBy": [],
            "facetOptions": [],
        }
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": GRID_SHA256}}
        url = (
            f"{PS_GRAPHQL}?operationName=categoryGridRetrieve"
            f"&variables={json.dumps(variables, separators=(',', ':'))}"
            f"&extensions={json.dumps(extensions, separators=(',', ':'))}"
        )
        resp = await self.client.get(
            url, headers=self._headers("categoryGridRetrieve"), timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    # ── Product extraction ────────────────────────────────────────────────────

    @staticmethod
    def extract_products(strand_data: dict) -> tuple[list, int]:
        """Extract product list from any known categoryStrandRetrieve shape."""
        # Format 1: direct products[]
        products = strand_data.get("products") or []
        if products:
            return products, strand_data.get("pageInfo", {}).get("totalCount", len(products))

        # Format 2: strands[] → each strand has products[]
        strands = strand_data.get("strands") or []
        if strands:
            out: list = []
            for s in strands:
                out.extend(s.get("products") or [])
            return out, len(out)

        # Format 3: concepts[] — two sub-formats:
        #   a) concept.defaultProduct has full product data (price, webctas, etc.)
        #   b) concept.products[] are stubs (only id); price/name/media are on concept
        concepts = strand_data.get("concepts") or []
        if concepts:
            out = []
            for c in concepts:
                c_name  = c.get("name", "")
                c_media = c.get("media") or []
                c_price = c.get("price") or {}  # price lives on concept in new_games format
                dp = c.get("defaultProduct") or {}
                if dp.get("id"):
                    # Full product — use it directly, fill missing name/media/price
                    merged = dict(dp)
                    merged.setdefault("name",  c_name)
                    merged.setdefault("media", c_media)
                    if not merged.get("price"):
                        merged["price"] = c_price
                    out.append(merged)
                else:
                    # Stub products — take first product's id; price/name/media from concept
                    p_list = c.get("products") or []
                    merged: dict = {}
                    if p_list:
                        merged["id"] = p_list[0].get("id", "")
                    merged["name"]  = c_name
                    merged["media"] = c_media
                    merged["price"] = c_price  # ← KEY: price is on the concept, not the stub
                    out.append(merged)
            total = strand_data.get("pageInfo", {}).get("totalCount", len(out))
            return out, total

        return [], 0

    @staticmethod
    def has_prices(products: list) -> bool:
        for p in products:
            pi = p.get("price") or {}
            if pi.get("basePrice") or pi.get("discountedPrice"):
                return True
            for cta in p.get("webctas") or []:
                cpi = cta.get("price") or {}
                if cpi.get("basePrice") or cpi.get("discountedPrice"):
                    return True
        return False

    async def fetch_all(self, category_id: str, max_pages: int = 30) -> list:
        """Fetch all products from a category (strand → grid fallback)."""
        all_products: list = []

        # Try strand first
        try:
            data = await self.fetch_strand_page(category_id, size=24, offset=0)
            sd = data.get("data", {}).get("categoryStrandRetrieve", {})
            products, total = self.extract_products(sd)
            if products and self.has_prices(products):
                all_products.extend(products)
                for page in range(1, max_pages):
                    if len(all_products) >= total:
                        break
                    try:
                        data2 = await self.fetch_strand_page(
                            category_id, size=24, offset=page * 24
                        )
                        sd2 = data2.get("data", {}).get("categoryStrandRetrieve", {})
                        p2, _ = self.extract_products(sd2)
                        if not p2:
                            break
                        all_products.extend(p2)
                    except Exception:
                        break
                return all_products
        except Exception as e:
            log.warning("Strand failed [%s]: %s", self.country, e)

        # Fallback to grid
        for page in range(max_pages):
            try:
                data = await self.fetch_grid_page(category_id, size=24, offset=page * 24)
                grid = data.get("data", {}).get("categoryGridRetrieve", {})
                products = grid.get("products", [])
                if not products:
                    break
                all_products.extend(products)
                total = grid.get("pageInfo", {}).get("totalCount", 0)
                if (page + 1) * 24 >= total:
                    break
            except Exception as e:
                log.error("Grid page %d [%s] failed: %s", page, self.country, e)
                break

        return all_products

    def parse_product(
        self, raw: dict, platform: str, allow_no_price: bool = False
    ) -> dict | None:
        """
        Parse a raw PS Store product.
        Returns None if name is missing.
        Returns None if price is 0 AND allow_no_price is False (default).
        Pass allow_no_price=True for preorders whose price is not yet announced.
        """
        try:
            name = raw.get("name", "")
            if not name:
                return None

            price_uah = 0.0
            discount_pct = 0

            # 1) webctas
            for cta in raw.get("webctas") or []:
                pi = cta.get("price") or {}
                base_str = pi.get("basePrice", "")
                disc_str = pi.get("discountedPrice", "")
                cur = detect_currency(base_str or disc_str)
                if cur not in ("UAH", "unknown"):
                    continue
                bv = parse_price_string(base_str)
                dv = parse_price_string(disc_str)
                if dv > 0:
                    price_uah = dv
                    if bv > dv:
                        discount_pct = round((1 - dv / bv) * 100)
                elif bv > 0:
                    price_uah = bv
                if price_uah > 0:
                    break

            # 2) direct price field
            if price_uah <= 0:
                price_obj = raw.get("price") or {}
                if isinstance(price_obj, dict):
                    base_str = price_obj.get("basePrice", "")
                    disc_str = price_obj.get("discountedPrice", "")
                    if detect_currency(base_str or disc_str) in ("UAH", "unknown"):
                        bv = parse_price_string(base_str)
                        dv = parse_price_string(disc_str)
                        if dv > 0:
                            price_uah = dv
                            if bv > dv:
                                discount_pct = round((1 - dv / bv) * 100)
                        elif bv > 0:
                            price_uah = bv

            # 3) skus
            if price_uah <= 0:
                skus = raw.get("skus") or []
                if skus:
                    pi = skus[0].get("price") or {}
                    if detect_currency(pi.get("basePrice", "")) in ("UAH", "unknown"):
                        pv = pi.get("basePriceValue", 0)
                        if pv:
                            price_uah = float(pv)

            if price_uah <= 0 and not allow_no_price:
                return None

            # Image
            image_url = ""
            for m in raw.get("media") or []:
                if m.get("role") in ("MASTER", "GAMEHUB_COVER_ART", "PORTRAIT_BANNER"):
                    image_url = m.get("url", "")
                    break
            if not image_url and raw.get("media"):
                image_url = raw["media"][0].get("url", "")

            # IDs
            original_id = raw.get("id", "") or ""
            concept = raw.get("concept") or {}
            if not original_id:
                original_id = str(concept.get("id", ""))

            # Release date → always ISO YYYY-MM-DD or None
            si = raw.get("storeInfo") or {}
            release_date = parse_release_date(
                si.get("releaseDate") or concept.get("releaseDate")
            )

            # Platform → normalised canonical string or None
            platforms = raw.get("platforms") or []
            platform = normalize_platform(platforms) if platforms else platform

            # Description
            desc = raw.get("description", "") or ""
            if len(desc) > 500:
                desc = desc[:497] + "..."

            # Genre (localizedGenreNames at product or concept level)
            genres = (
                raw.get("localizedGenreNames")
                or concept.get("localizedGenreNames")
                or []
            )
            genre = ", ".join(str(g) for g in genres[:2]) if genres else ""

            # PS Plus required
            requires_ps_plus = bool(
                raw.get("requiresSubscription")
                or raw.get("requiresPSPlus")
                or raw.get("psPlus")
                or (raw.get("plus") or {}).get("required")
                or any(
                    (s or {}).get("required") or (s or {}).get("isRequired")
                    for s in (raw.get("subscriptions") or [])
                )
            )

            # Discount end date (from first webcta price or promotion data)
            discount_until: str | None = None
            for cta in raw.get("webctas") or []:
                pi = cta.get("price") or {}
                end = (
                    pi.get("promotionEndDate")
                    or pi.get("discountEndDate")
                    or pi.get("endDate")
                )
                if end:
                    # Normalise to YYYY-MM-DD
                    discount_until = str(end)[:10]
                    break

            return {
                "title": name,
                "description": desc,
                "image_url": image_url,
                "price_uah": price_uah,
                "platform": platform,
                "rating": 0,
                "is_featured": 0,
                "discount_pct": discount_pct,
                "original_id": original_id,
                "release_date": release_date,
                "product_type": "game",
                "is_preorder": 0,
                "region": self.region,
                "genre": genre,
                "requires_ps_plus": int(requires_ps_plus),
                "discount_until": discount_until,
            }
        except Exception as e:
            log.error("parse_product error: %s", e)
            return None

    def parse_price_try(self, raw: dict) -> float:
        """Extract TRY price from a raw PS product dict."""
        for cta in raw.get("webctas") or []:
            pi = cta.get("price") or {}
            base_str = pi.get("basePrice", "")
            disc_str = pi.get("discountedPrice", "")
            if detect_currency(base_str or disc_str) != "TRY":
                continue
            dv = parse_price_string(disc_str)
            bv = parse_price_string(base_str)
            price = dv if dv > 0 else bv
            if price > 0:
                return price

        price_obj = raw.get("price") or {}
        if isinstance(price_obj, dict):
            base_str = price_obj.get("basePrice", "")
            disc_str = price_obj.get("discountedPrice", "")
            if detect_currency(base_str or disc_str) == "TRY":
                dv = parse_price_string(disc_str)
                bv = parse_price_string(base_str)
                price = dv if dv > 0 else bv
                if price > 0:
                    return price
        return 0.0

    # ── Edition scraping ──────────────────────────────────────────────────────

    async def parse_editions(self, product_url: str, region: str) -> list[dict]:
        """
        Parse all editions/SKUs from a PS Store product page URL.

        Strategy:
          1. Fetch HTML via get_page()
          2. Extract __NEXT_DATA__ → pageProps.batarangs.upsells  (primary — SSR data)
          3. Extract __NEXT_DATA__ → initialApolloState / page props  (legacy)
          4. Fall back to application/json script tags
          5. Fall back to window.__APOLLO_STATE__ / __STORE_STATE__

        Each returned dict:
          {
            edition_name : str,
            price        : float,   # local currency
            old_price    : float | None,
            discount_pct : int,
            platform     : str,
            ps_store_url : str,
            is_free      : bool,
            region       : str,
            currency     : str,     # "UAH" | "TRY" | ...
          }
        Returns empty list if page is unavailable or no editions found.
        """
        html = await self.get_page(product_url)
        if not html:
            return []

        editions: list[dict] = []

        # ── Strategy 1 + 2: __NEXT_DATA__ (batarangs primary, page props fallback) ──
        m = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            html, re.DOTALL,
        )
        if m:
            try:
                data = json.loads(m.group(1))
                pp = (data.get("props") or {}).get("pageProps") or {}

                # Strategy 1: batarangs.upsells — PS Store SSR component cache
                batarangs = pp.get("batarangs") or {}
                if batarangs:
                    editions = self._editions_from_batarangs(batarangs, region)

                # Strategy 2: legacy initialApolloState / page props shape
                if not editions:
                    editions = self._editions_from_next_data(data, product_url, region)

            except Exception as e:
                self._log(f"⚠️ __NEXT_DATA__ parse error: {e}")

        # ── Strategy 3: application/json script tags ──────────────────────────
        if not editions:
            for tag_m in re.finditer(
                r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
                html, re.DOTALL,
            ):
                try:
                    blob = json.loads(tag_m.group(1))
                    editions = self._editions_from_blob(blob, product_url, region)
                    if editions:
                        break
                except Exception:
                    continue

        # ── Strategy 4: window state variables ───────────────────────────────
        if not editions:
            for var_m in re.finditer(
                r'window\.__(?:APOLLO_STATE|STORE_STATE|STATE)__\s*=\s*({.*?})\s*;',
                html, re.DOTALL,
            ):
                try:
                    blob = json.loads(var_m.group(1))
                    editions = self._editions_from_blob(blob, product_url, region)
                    if editions:
                        break
                except Exception:
                    continue

        return editions

    # ── Edition helpers ───────────────────────────────────────────────────────

    def _editions_from_batarangs(
        self, batarangs: dict, region: str
    ) -> list[dict]:
        """
        Extract editions from PS Store's 'batarangs' SSR component cache.

        PS Store product pages embed component data as JSON inside
        <script type="application/json"> tags within each batarang's .text field.
        The 'upsells' batarang contains the full Apollo cache for all editions
        of the game: Product:* nodes (names/platforms) and GameCTA:* nodes (prices).

        Returns [] if upsells are missing or fewer than 2 editions found.
        """
        upsells = batarangs.get("upsells") or {}
        text = upsells.get("text", "") if isinstance(upsells, dict) else ""
        if not text:
            return []

        # Embedded JSON inside the batarang HTML text
        m = re.search(
            r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
            text, re.DOTALL,
        )
        if not m:
            return []

        try:
            data = json.loads(m.group(1))
        except Exception as e:
            self._log(f"⚠️ batarangs JSON parse error: {e}")
            return []

        cache = data.get("cache") or {}
        if not cache:
            return []

        locale = "tr-tr" if self.country == "TR" else "ru-ua"
        default_currency = "TRY" if self.country == "TR" else "UAH"

        # ── Product nodes: id → {name, platforms} ────────────────────────────
        # Skip demos — they have topCategory == "DEMO" and are not purchasable
        _SKIP_CATEGORIES = {"DEMO", "DEMO_FULL_GAME"}
        product_info: dict[str, dict] = {}
        for key, val in cache.items():
            if not key.startswith("Product:") or not isinstance(val, dict):
                continue
            pid = val.get("id", "")
            if not pid:
                continue
            if val.get("topCategory") in _SKIP_CATEGORIES:
                continue
            product_info[pid] = {
                "name":      val.get("name") or val.get("invariantName", ""),
                "platforms": val.get("platforms") or [],
            }

        # ── GameCTA nodes: product_id → price info ────────────────────────────
        # Capture ADD_TO_CART (normal purchase) and PREORDER (preorder) actions.
        # Excluded: DOWNLOAD_DEMO, DOWNLOAD (non-store items), etc.
        # Key formats:
        #   GameCTA:ADD_TO_CART:ADD_TO_CART:{sku_id}:OUTRIGHT  — normal sale
        #   GameCTA:PREORDER:BUY_NOW:{sku_id}:OUTRIGHT         — preorder
        # sku_id = {product_id}-E{digits}  (e.g. EP9000-…-SAROS00000000000-E002)
        _PURCHASABLE_CTA_PREFIXES = ("GameCTA:ADD_TO_CART:", "GameCTA:PREORDER:")
        price_info: dict[str, dict] = {}
        for key, val in cache.items():
            if not any(key.startswith(p) for p in _PURCHASABLE_CTA_PREFIXES):
                continue
            if not isinstance(val, dict):
                continue
            parts = key.split(":")
            if len(parts) < 4:
                continue
            sku_id = parts[3]
            # Strip trailing SKU suffix to recover product_id
            prod_id = re.sub(r"-E\d+$", "", sku_id)

            price_obj = val.get("price") or {}
            if price_obj:
                base_str = price_obj.get("basePrice", "")
                disc_str = price_obj.get("discountedPrice", "")
                currency = price_obj.get("currencyCode", default_currency)

                base_val = parse_price_string(base_str)
                if not base_val:
                    bpv = price_obj.get("basePriceValue", 0)
                    base_val = float(bpv) / 100 if bpv else 0.0

                disc_val = parse_price_string(disc_str)
                if not disc_val:
                    dpv = price_obj.get("discountedValue", 0)
                    disc_val = float(dpv) / 100 if dpv else 0.0

                is_free = bool(price_obj.get("isFree"))
            else:
                # Fallback: local.priceOrText
                local = val.get("local") or {}
                price_str = local.get("priceOrText", "")
                orig_str  = local.get("originalPrice", "")
                base_val  = parse_price_string(price_str)
                disc_val  = 0.0
                is_free   = base_val == 0 and bool(price_str)
                currency  = default_currency
                # Try to detect old price from originalPrice field
                old_candidate = parse_price_string(orig_str)
                if old_candidate > base_val > 0:
                    disc_val  = base_val
                    base_val  = old_candidate

            if disc_val > 0 and base_val > disc_val:
                price        = disc_val
                old_price    = base_val
                discount_pct = round((1 - disc_val / base_val) * 100)
            elif base_val > 0:
                price        = base_val
                old_price    = None
                discount_pct = 0
            else:
                price        = 0.0
                old_price    = None
                discount_pct = 0

            # Prefer entry with actual price over price=0
            if prod_id not in price_info or price > 0:
                price_info[prod_id] = {
                    "price":        price,
                    "old_price":    old_price,
                    "discount_pct": discount_pct,
                    "is_free":      is_free,
                    "currency":     currency,
                }

        # ── Merge and build edition list ──────────────────────────────────────
        editions: list[dict] = []
        for pid, pinfo in product_info.items():
            name = pinfo["name"]
            if not name:
                continue
            platforms = pinfo["platforms"]
            platform_str = (
                ", ".join(str(p) for p in platforms)
                if isinstance(platforms, list) and platforms
                else "PS4/PS5"
            )
            pdata = price_info.get(pid, {})
            price   = pdata.get("price", 0)
            is_free = pdata.get("is_free", False)

            # Skip editions with no price that are not explicitly free —
            # these are usually cross-region duplicates or unlisted bundles
            # that have no GameCTA in this region's upsells cache.
            if price == 0 and not is_free:
                continue

            editions.append({
                "edition_name": name,
                "price":        price,
                "old_price":    pdata.get("old_price"),
                "discount_pct": pdata.get("discount_pct", 0),
                "platform":     platform_str,
                "ps_store_url": f"https://store.playstation.com/{locale}/product/{pid}",
                "is_free":      is_free,
                "region":       region,
                "currency":     pdata.get("currency", default_currency),
            })

        return editions

    def _editions_from_next_data(
        self, data: dict, product_url: str, region: str
    ) -> list[dict]:
        """Navigate __NEXT_DATA__ → props.pageProps → find skus/variants."""
        page_props = (data.get("props") or {}).get("pageProps") or {}

        for key in ("product", "concept", "productData", "data"):
            node = page_props.get(key) or {}
            if not node:
                continue
            skus = node.get("skus") or node.get("variants") or []
            if skus:
                return self._parse_sku_list(skus, product_url, region)
            # one level deeper
            for sub in ("product", "defaultProduct", "concept"):
                sub_node = node.get(sub) or {}
                skus = sub_node.get("skus") or sub_node.get("variants") or []
                if skus:
                    return self._parse_sku_list(skus, product_url, region)
        return []

    def _editions_from_blob(
        self, blob, product_url: str, region: str
    ) -> list[dict]:
        """Recursively search a JSON blob for a skus/variants array."""
        skus = self._find_list_by_key(blob, ("skus", "variants"), max_depth=6)
        return self._parse_sku_list(skus or [], product_url, region)

    def _find_list_by_key(self, obj, keys: tuple, max_depth: int = 5) -> list | None:
        """Depth-first search for the first non-empty list under any of keys."""
        if max_depth <= 0:
            return None
        if isinstance(obj, dict):
            for k in keys:
                v = obj.get(k)
                if isinstance(v, list) and v:
                    return v
            for v in obj.values():
                result = self._find_list_by_key(v, keys, max_depth - 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_list_by_key(item, keys, max_depth - 1)
                if result:
                    return result
        return None

    def _parse_sku_list(
        self, skus: list, product_url: str, region: str
    ) -> list[dict]:
        """Convert raw SKU dicts from PS Store JSON into our edition format."""
        editions: list[dict] = []
        for sku in skus:
            if not isinstance(sku, dict):
                continue

            name = (
                sku.get("name")
                or sku.get("localizedName")
                or sku.get("skuTitle")
                or sku.get("id", "")
            )
            if not name:
                continue

            price_info = sku.get("price") or {}
            base_str   = price_info.get("basePrice", "")
            disc_str   = price_info.get("discountedPrice", "")
            base_val   = (
                parse_price_string(base_str)
                or float(price_info.get("basePriceValue") or 0)
            )
            disc_val   = (
                parse_price_string(disc_str)
                or float(price_info.get("discountedPriceValue") or 0)
            )

            if disc_val > 0 and base_val > disc_val:
                price        = disc_val
                old_price    = base_val
                discount_pct = round((1 - disc_val / base_val) * 100)
            elif base_val > 0:
                price        = base_val
                old_price    = None
                discount_pct = 0
            else:
                price        = disc_val
                old_price    = None
                discount_pct = 0

            is_free  = price == 0 or str(base_str).lower() in ("free", "бесплатно", "безкоштовно")
            currency = detect_currency(base_str or disc_str) or "UAH"

            platforms = sku.get("platforms") or []
            platform  = (
                ", ".join(str(p) for p in platforms)
                if isinstance(platforms, list) and platforms
                else sku.get("platform", "PS4/PS5")
            )

            editions.append({
                "edition_name": str(name),
                "price":        price,
                "old_price":    old_price,
                "discount_pct": discount_pct,
                "platform":     platform,
                "ps_store_url": product_url,
                "is_free":      is_free,
                "region":       region,
                "currency":     currency,
            })

        return editions

    # ── DB operations ─────────────────────────────────────────────────────────

    async def reset_sales(self) -> None:
        """
        Reset all discounts for self.region.

          UPDATE products    SET discount_pct=0, old_price=NULL        WHERE region=?
          UPDATE game_editions SET discount_pct=0,
                                   old_price_uah=NULL, old_price_try=NULL WHERE region=?
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                "UPDATE products SET discount_pct=0, old_price=NULL WHERE region=?",
                (self.region,),
            )
            await conn.execute(
                """UPDATE game_editions
                   SET discount_pct=0, old_price_uah=NULL, old_price_try=NULL
                   WHERE region=?""",
                (self.region,),
            )
            await conn.commit()
        self._log(f"✅ Скидки сброшены для региона {self.region}")

    async def save_product(
        self,
        product_data: dict,
        editions: list[dict],
        conn: "aiosqlite.Connection | None" = None,
    ) -> int:
        """
        Upsert a product and optionally its editions.

        Lookup order:
          1. original_id  (preferred, globally unique)
          2. title + region  (fallback)

        If editions is non-empty:
          - DELETE old game_editions for this product + region
          - INSERT new editions (prices auto-converted to BYN/BYN_TR)
          - SET has_editions=1 on the product row

        If editions is empty:
          - Updates price_uah / price_byn / discount_pct directly.

        Returns the product's DB id.
        """
        own_conn = conn is None
        if own_conn:
            conn = await aiosqlite.connect(self._db_path)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")

        try:
            product_data = validate_product(product_data)
            ps = await get_price_settings(conn)

            title             = product_data.get("title", "")
            description       = product_data.get("description", "")
            image_url         = product_data.get("image_url", "")
            price_uah         = product_data.get("price_uah") or 0
            price_try         = product_data.get("price_try") or 0
            platform          = product_data.get("platform") or None
            rating            = product_data.get("rating", 0)
            is_featured       = product_data.get("is_featured", 0)
            discount_pct      = product_data.get("discount_pct", 0)
            original_id       = product_data.get("original_id", "")
            release_date      = product_data.get("release_date")
            product_type      = product_data.get("product_type", "game")
            is_preorder       = product_data.get("is_preorder", 0)
            region            = product_data.get("region", self.region)
            category_id       = product_data.get("category_id", 1)
            task_type         = product_data.get("task_type", "")
            has_editions      = 1 if editions else 0
            genre             = product_data.get("genre") or ""
            requires_ps_plus  = int(bool(product_data.get("requires_ps_plus", 0)))
            discount_until    = product_data.get("discount_until")

            # Auto-calculate BYN (respects manual overrides in product_data)
            byn_calc   = calc_price_byn(
                {
                    "price_uah":    price_uah,
                    "price_try":    price_try,
                    "product_type": product_type,
                    "price_byn":    product_data.get("price_byn"),
                    "price_byn_tr": product_data.get("price_byn_tr"),
                },
                ps,
            )
            price_byn    = byn_calc.get("price_byn")
            price_byn_tr = byn_calc.get("price_byn_tr")

            # ── Find existing product ─────────────────────────────────────────
            product_id: int | None = None
            if original_id:
                async with conn.execute(
                    "SELECT id FROM products WHERE original_id=?", (original_id,)
                ) as cur:
                    row = await cur.fetchone()
                    if row:
                        product_id = row[0]

            if product_id is None:
                async with conn.execute(
                    "SELECT id FROM products WHERE title=? AND region=?", (title, region)
                ) as cur:
                    row = await cur.fetchone()
                    if row:
                        product_id = row[0]

            # ── INSERT or UPDATE ──────────────────────────────────────────────
            if product_id is not None:
                await conn.execute(
                    """UPDATE products SET
                         title=?,
                         description=?,
                         image_url=COALESCE(NULLIF(?, ''), image_url),
                         price_uah=?,
                         price_byn=COALESCE(?, price_byn),
                         price_byn_tr=COALESCE(?, price_byn_tr),
                         platform=?,
                         discount_pct=?,
                         discount_until=COALESCE(?, discount_until),
                         is_preorder=?,
                         has_editions=?,
                         task_type=COALESCE(NULLIF(?, ''), task_type),
                         release_date=COALESCE(?, release_date),
                         genre=COALESCE(NULLIF(?, ''), genre),
                         requires_ps_plus=?,
                         is_active=1,
                         updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (
                        title, description, image_url,
                        price_uah,
                        price_byn, price_byn_tr,
                        platform, discount_pct, discount_until,
                        is_preorder, has_editions,
                        task_type, release_date,
                        genre, requires_ps_plus,
                        product_id,
                    ),
                )
            else:
                cur2 = await conn.execute(
                    """INSERT INTO products
                         (category_id, title, description, image_url,
                          price_uah, price_byn, price_byn_tr,
                          platform, rating, is_featured, is_active,
                          discount_pct, discount_until, original_id, release_date,
                          product_type, is_preorder, has_editions, region, task_type,
                          genre, requires_ps_plus)
                       VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        category_id, title, description, image_url,
                        price_uah, price_byn, price_byn_tr,
                        platform, rating, is_featured,
                        discount_pct, discount_until, original_id, release_date,
                        product_type, is_preorder, has_editions, region, task_type,
                        genre, requires_ps_plus,
                    ),
                )
                product_id = cur2.lastrowid

            # ── Editions ──────────────────────────────────────────────────────
            if editions:
                await conn.execute(
                    "DELETE FROM game_editions WHERE parent_product_id=? AND region=?",
                    (product_id, region),
                )
                for ed in editions:
                    currency  = ed.get("currency", "UAH")
                    raw_price = float(ed.get("price") or 0)
                    raw_old   = ed.get("old_price")

                    if currency == "TRY":
                        ed_price_uah = None
                        ed_old_uah   = None
                        ed_price_try = raw_price
                        ed_old_try   = float(raw_old) if raw_old is not None else None
                    else:
                        ed_price_uah = raw_price
                        ed_old_uah   = float(raw_old) if raw_old is not None else None
                        ed_price_try = None
                        ed_old_try   = None

                    ed_byn = calc_price_byn(
                        {
                            "price_uah":    ed_price_uah or 0,
                            "price_try":    ed_price_try or 0,
                            "product_type": "game",
                            "price_byn":    None,
                            "price_byn_tr": None,
                        },
                        ps,
                    )

                    await conn.execute(
                        """INSERT INTO game_editions
                             (parent_product_id, edition_name,
                              price_uah, price_try, price_byn, price_byn_tr,
                              old_price_uah, old_price_try,
                              discount_pct, platform, ps_store_url,
                              region, is_free, is_active)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                        (
                            product_id,
                            ed.get("edition_name", ""),
                            ed_price_uah, ed_price_try,
                            ed_byn.get("price_byn"), ed_byn.get("price_byn_tr"),
                            ed_old_uah, ed_old_try,
                            ed.get("discount_pct", 0),
                            ed.get("platform", "PS4/PS5"),
                            ed.get("ps_store_url", ""),
                            region,
                            1 if ed.get("is_free") else 0,
                        ),
                    )

            if own_conn:
                await conn.commit()

            n_ed = len(editions)
            if n_ed:
                self._log(f"✅ {title} — {n_ed} эдишенов")
            else:
                self._log(f"✅ {title}")

            return product_id  # type: ignore[return-value]

        finally:
            if own_conn:
                await conn.close()

    async def update_parser_log(
        self,
        log_id: int,
        status: str,
        added: int = 0,
        updated: int = 0,
        errors: int = 0,
        details: str = "",
    ) -> None:
        """Update a parser_log row with final stats and finished_at timestamp."""
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """UPDATE parser_log
                   SET finished_at=CURRENT_TIMESTAMP, status=?,
                       products_added=?, products_updated=?,
                       errors_count=?, details=?
                   WHERE id=?""",
                (status, added, updated, errors, details, log_id),
            )
            await conn.commit()

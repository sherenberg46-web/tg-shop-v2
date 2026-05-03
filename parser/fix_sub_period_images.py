"""
Finds per-period cover images for PS Plus Extra and Deluxe subscriptions
via the PlayStation Store Tumbler API and uploads them to Railway.

Products to fix:
  ID 33  PS Plus Extra   – 1 месяц
  ID 36  PS Plus Extra   – 3 месяца
  ID 37  PS Plus Extra   – 12 месяцев
  ID 34  PS Plus Deluxe  – 1 месяц
  ID 38  PS Plus Deluxe  – 3 месяца
  ID 39  PS Plus Deluxe  – 12 месяцев
"""

import asyncio
import httpx

API   = "https://tg-shop-production-1b03.up.railway.app/api/v1"
TOKEN = "ac9689e2272427085e35b9d3e3e8bed88cb3434828b43b86fc0596cad4c6e270"
HDR   = {"x-admin-token": TOKEN}

SEARCH_URL = (
    "https://store.playstation.com/store/api/chihiro/00_09_000/tumbler"
    "/UA/ru/999/{query}?suggested_size=5"
)
PSHEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# (product_id, search_query)
TARGETS = [
    (33, "PS Plus Extra 1 Month"),
    (36, "PS Plus Extra 3 Months"),
    (37, "PS Plus Extra 12 Months"),
    (34, "PS Plus Deluxe 1 Month"),
    (38, "PS Plus Deluxe 3 Months"),
    (39, "PS Plus Deluxe 12 Months"),
]


async def search_image(client: httpx.AsyncClient, query: str) -> str | None:
    url = SEARCH_URL.format(query=query.replace(" ", "%20"))
    try:
        r = await client.get(url, headers=PSHEADERS, timeout=15, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
        links = data.get("links") or []
        for item in links:
            img = (item.get("images") or [{}])[0].get("url")
            name = item.get("name", "")
            print("  candidate:", name, "->", (img or "")[:60])
            if img:
                return img
    except Exception as e:
        print("  search error:", e)
    return None


async def upload_bytes(client: httpx.AsyncClient, data: bytes, ext: str) -> str:
    resp = await client.post(
        f"{API}/admin/upload",
        headers=HDR,
        files={"file": ("img" + ext, data, "image/png")},
        timeout=30,
    )
    resp.raise_for_status()
    path = resp.json()["url"]
    return "https://tg-shop-production-1b03.up.railway.app" + path


async def get_product(client: httpx.AsyncClient, pid: int) -> dict:
    r = await client.get(
        f"{API}/admin/products",
        headers=HDR,
        params={"limit": 100},
        timeout=15,
    )
    r.raise_for_status()
    items = r.json()["items"]
    return next(p for p in items if p["id"] == pid)


async def update_image(client: httpx.AsyncClient, pid: int, image_url: str) -> None:
    p = await get_product(client, pid)
    payload = {
        "category_id":   p["category_id"],
        "title":         p["title"],
        "description":   p.get("description"),
        "image_url":     image_url,
        "price_uah":     p["price_uah"],
        "price_try":     p["price_try"],
        "price_inr":     p["price_inr"],
        "price_pln":     p["price_pln"],
        "platform":      p.get("platform", "PS4, PS5"),
        "rating":        p.get("rating", 4.5),
        "is_featured":   p.get("is_featured", False),
        "is_active":     p.get("is_active", True),
        "discount_pct":  p.get("discount_pct", 0.0),
        "discount_until": p.get("discount_until"),
        "product_type":  p.get("product_type", "subscription"),
        "is_preorder":   p.get("is_preorder", False),
    }
    r = await client.put(
        f"{API}/admin/products/{pid}",
        headers={**HDR, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()


async def run():
    img_cache: dict[str, bytes] = {}

    async with httpx.AsyncClient(verify=False) as client:
        for pid, query in TARGETS:
            print(f"\n=== ID={pid} | {query} ===")

            img_url = await search_image(client, query)
            if not img_url:
                print("  no image found, skipping")
                continue

            # Download image
            if img_url not in img_cache:
                try:
                    r = await client.get(img_url, timeout=20, follow_redirects=True)
                    r.raise_for_status()
                    img_cache[img_url] = r.content
                    print(f"  downloaded {len(r.content)//1024} KB")
                except Exception as e:
                    print("  download error:", e)
                    continue

            # Upload to Railway
            try:
                hosted = await upload_bytes(client, img_cache[img_url], ".png")
                print("  uploaded:", hosted)
            except Exception as e:
                print("  upload error:", e)
                continue

            # Update product
            try:
                await update_image(client, pid, hosted)
                print("  updated OK")
            except Exception as e:
                print("  update error:", e)

    print("\nDone.")


asyncio.run(run())

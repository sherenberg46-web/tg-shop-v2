import asyncio
import httpx

API   = "https://tg-shop-production-1b03.up.railway.app/api/v1"
TOKEN = "ac9689e2272427085e35b9d3e3e8bed88cb3434828b43b86fc0596cad4c6e270"
HDR   = {"x-admin-token": TOKEN}

EXTRA_IMG   = "https://vulcan.dl.playstation.net/ap/rnd/202205/0613/Sfyd8Ru6pLqK3VS4TdX082wN.png"
DELUXE_IMG  = "https://vulcan.dl.playstation.net/ap/rnd/202205/1807/cMifY7nhZVLRgVpXMpMBa5Nh.png"
EA_1M_IMG   = "https://vulcan.dl.playstation.net/ap/rnd/202404/0200/b19a8ff3035f567e179522aac0cd4ef7439e710d9d6148bb.png"
EA_12M_IMG  = "https://vulcan.dl.playstation.net/ap/rnd/202404/0200/eb8ad6d56b37511082b36adf6f00fb5fd50cea654cd518ae.png"

PRODUCTS = [
    (36, 2, "PS Plus Extra - 3 mesyaca",    None,  824.0, 1065.0, 1999.0, 135.0, "PS4, PS5", 4.7, False, True, 0.0, "subscription", EXTRA_IMG),
    (37, 2, "PS Plus Extra - 12 mesyacev",  None, 2469.0, 3240.0, 5924.0, 405.0, "PS4, PS5", 4.8, True,  True, 0.0, "subscription", EXTRA_IMG),
    (38, 2, "PS Plus Deluxe - 3 mesyaca",   None, 1099.0, 1330.0, 2499.0, 168.0, "PS4, PS5", 4.7, False, True, 0.0, "subscription", DELUXE_IMG),
    (39, 2, "PS Plus Deluxe - 12 mesyacev", None, 3299.0, 3990.0, 7499.0, 504.0, "PS4, PS5", 4.8, True,  True, 0.0, "subscription", DELUXE_IMG),
    (40, 3, "EA Play - 1 mesyac",           None,  219.0,  139.0,  199.0,  17.0, "PS4, PS5", 4.5, False, True, 0.0, "subscription", EA_1M_IMG),
    (41, 3, "EA Play - 12 mesyacev",        None, 1099.0,  699.0,  999.0,  85.0, "PS4, PS5", 4.6, True,  True, 0.0, "subscription", EA_12M_IMG),
]

# We'll keep original titles from the DB -- only image_url changes
# Fetch them first so we don't overwrite titles
ORIG_TITLES = {
    36: "PS Plus Extra \u2013 3 \u043c\u0435\u0441\u044f\u0446\u0430",
    37: "PS Plus Extra \u2013 12 \u043c\u0435\u0441\u044f\u0446\u0435\u0432",
    38: "PS Plus Deluxe \u2013 3 \u043c\u0435\u0441\u044f\u0446\u0430",
    39: "PS Plus Deluxe \u2013 12 \u043c\u0435\u0441\u044f\u0446\u0435\u0432",
    40: "EA Play \u2013 1 \u043c\u0435\u0441\u044f\u0446",
    41: "EA Play \u2013 12 \u043c\u0435\u0441\u044f\u0446\u0435\u0432",
}


async def upload_bytes(client, data, ext):
    resp = await client.post(
        f"{API}/admin/upload",
        headers=HDR,
        files={"file": ("img" + ext, data, "image/png")},
        timeout=30,
    )
    resp.raise_for_status()
    path = resp.json()["url"]
    return "https://tg-shop-production-1b03.up.railway.app" + path


async def run():
    cache = {}
    async with httpx.AsyncClient() as client:
        # First fetch current product data from Railway
        resp = await client.get(
            f"{API}/admin/products",
            headers={**HDR, "limit": "100"},
            params={"limit": 100},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json()["items"]
        db_products = {p["id"]: p for p in items}

        for row in PRODUCTS:
            pid, cat_id, _, desc, uah, try_, inr, pln, platform, rating, featured, active, disc, ptype, src = row
            print("Processing id=" + str(pid))

            # Download image
            if src not in cache:
                r = await client.get(src, timeout=20, follow_redirects=True)
                r.raise_for_status()
                cache[src] = r.content
                print("  downloaded " + str(len(r.content)//1024) + " KB")
            data = cache[src]

            # Upload
            try:
                hosted = await upload_bytes(client, data, ".png")
                print("  uploaded: " + hosted)
            except Exception as e:
                print("  UPLOAD ERROR: " + str(e))
                continue

            # Build payload keeping original title from DB
            orig = db_products.get(pid, {})
            title = orig.get("title") or ORIG_TITLES.get(pid, "subscription")

            payload = {
                "category_id":   cat_id,
                "title":         title,
                "description":   orig.get("description") or desc,
                "image_url":     hosted,
                "price_uah":     uah,
                "price_try":     try_,
                "price_inr":     inr,
                "price_pln":     pln,
                "platform":      platform,
                "rating":        rating,
                "is_featured":   featured,
                "is_active":     active,
                "discount_pct":  disc,
                "discount_until": None,
                "product_type":  ptype,
                "is_preorder":   False,
            }

            resp2 = await client.put(
                f"{API}/admin/products/{pid}",
                headers={**HDR, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp2.raise_for_status()
            print("  updated OK")

    print("All done.")


asyncio.run(run())

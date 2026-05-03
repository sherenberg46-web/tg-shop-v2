"""
Seed the SQLite database with schema + sample data.
Run: python database/seed.py
"""
import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "database/shop.db")
SCHEMA   = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    with open(SCHEMA, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    print("[+] Schema applied")


def seed_categories(conn: sqlite3.Connection) -> None:
    rows = [
        ("PlayStation Games",  "ps-games",  "🎮", 1),
        ("PS Plus",            "ps-plus",   "⭐", 2),
        ("Gift Cards",         "gift-cards","💳", 3),
        ("DLC & Add-ons",      "dlc",       "🧩", 4),
        ("In-Game Currency",   "currency",  "💰", 5),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name, slug, icon, sort_order) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()
    print(f"[+] {len(rows)} categories seeded")


def seed_products(conn: sqlite3.Connection) -> None:
    cat = {r["slug"]: r["id"] for r in conn.execute("SELECT id, slug FROM categories")}

    products = [
        # (category_slug, title, description, image_url, price_uah, price_try, price_inr, price_pln, original_id, platform, rating, is_featured)
        ("ps-games", "God of War Ragnarök", "Continue the Norse saga.", "https://placehold.co/300x400?text=GoW", 1299, 249, 3499, 199, "CUSA34575_00", "PS5", 4.9, 1),
        ("ps-games", "Spider-Man 2", "Be greater. Together.", "https://placehold.co/300x400?text=SM2",  1199, 229, 3299, 179, "PPSA07950_00", "PS5", 4.8, 1),
        ("ps-games", "Hogwarts Legacy", "An open-world RPG.", "https://placehold.co/300x400?text=HL",   899,  179, 2499, 149, "PPSA04529_00", "PS5", 4.7, 0),
        ("ps-plus", "PS Plus Essential 1M", "1 month membership.", "https://placehold.co/300x400?text=PS%2B", 219, 49, 699, 39, "HP0700-CUSA00562_00-PSPESSENTIAL001M", "PSN", 4.5, 1),
        ("ps-plus", "PS Plus Extra 3M",   "3 months Extra.",    "https://placehold.co/300x400?text=PS%2B3", 649, 119, 1999, 109, "HP0700-CUSA00562_00-PSPEXTRA003M", "PSN", 4.6, 0),
        ("gift-cards", "PSN Card $10",    "$10 wallet top-up.", "https://placehold.co/300x400?text=%2410", 410, 89, 1199, 49, "PSN_GC_10USD", "PSN", 4.8, 0),
        ("gift-cards", "PSN Card $25",    "$25 wallet top-up.", "https://placehold.co/300x400?text=%2425", 999, 199, 2899, 119, "PSN_GC_25USD", "PSN", 4.8, 1),
        ("dlc", "Elden Ring – Shadow of the Erdtree", "Massive DLC expansion.", "https://placehold.co/300x400?text=Elden", 699, 139, 1999, 89, "PPSA01556_00_DLC01", "PS5", 4.7, 1),
        ("currency", "GTA$ 1,000,000 Shark Card", "In-game currency.", "https://placehold.co/300x400?text=Shark", 299, 69, 999, 39, "CUSA00419_00_SHARK1M", "PS4", 4.3, 0),
    ]

    conn.executemany(
        """INSERT OR IGNORE INTO products
           (category_id, title, description, image_url,
            price_uah, price_try, price_inr, price_pln,
            original_id, platform, rating, is_featured)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(cat[p[0]], *p[1:]) for p in products],
    )
    conn.commit()
    print(f"[+] {len(products)} products seeded")


def main() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = get_conn()
    apply_schema(conn)
    seed_categories(conn)
    seed_products(conn)
    conn.close()
    print(f"\n[OK] Database ready at {DB_PATH}")


if __name__ == "__main__":
    main()

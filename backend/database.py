"""Async SQLite helpers (aiosqlite)."""
import aiosqlite
from pathlib import Path
from backend.config import settings

DB_PATH = Path(settings.DB_PATH)
SCHEMA = Path(__file__).parent / "schema.sql"


async def get_db() -> aiosqlite.Connection:
    """FastAPI dependency – yields an open DB connection."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn


async def init_db() -> None:
    """Create tables if they don't exist yet (called on startup)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        sql = SCHEMA.read_text(encoding="utf-8")
        await conn.executescript(sql)
        await conn.commit()
        # Run migrations for existing databases
        await _migrate(conn)


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Add new columns to existing databases (idempotent)."""
    migrations = [
        "ALTER TABLE products ADD COLUMN discount_pct REAL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN discount_until DATETIME",
        "ALTER TABLE orders ADD COLUMN account_type TEXT DEFAULT 'no_account'",
        "ALTER TABLE orders ADD COLUMN ps_email TEXT",
        "ALTER TABLE orders ADD COLUMN ps_password TEXT",
        "ALTER TABLE products ADD COLUMN release_date DATE",
        "ALTER TABLE products ADD COLUMN product_type TEXT DEFAULT 'game'",
        "ALTER TABLE products ADD COLUMN is_preorder INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN price_try REAL",
        """CREATE TABLE IF NOT EXISTS product_editions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name       TEXT    NOT NULL,
            price_uah  REAL,
            price_try  REAL,
            price_inr  REAL,
            price_pln  REAL,
            is_default INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_editions_product ON product_editions(product_id)",
        """CREATE TABLE IF NOT EXISTS admin_settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS admin_banners (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL DEFAULT '',
            subtitle   TEXT NOT NULL DEFAULT '',
            image_url  TEXT NOT NULL DEFAULT '',
            link_url   TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE admin_banners ADD COLUMN link_ua TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE admin_banners ADD COLUMN link_tr TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE admin_banners ADD COLUMN gradient TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE admin_banners ADD COLUMN collection_slug TEXT NOT NULL DEFAULT ''",
        """CREATE TABLE IF NOT EXISTS collections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            slug        TEXT NOT NULL UNIQUE,
            description TEXT,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS collection_products (
            collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
            product_id    INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            sort_order    INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (collection_id, product_id)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_col_products ON collection_products(collection_id, sort_order)",
        "ALTER TABLE products ADD COLUMN price_byn INTEGER",
        "ALTER TABLE products ADD COLUMN price_byn_tr INTEGER",
        "ALTER TABLE products ADD COLUMN region TEXT DEFAULT 'UA'",
        "ALTER TABLE products ADD COLUMN has_editions INTEGER DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS game_editions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            edition_name      TEXT    NOT NULL,
            price_uah         REAL,
            price_try         REAL,
            price_byn         REAL,
            price_byn_tr      REAL,
            old_price_uah     REAL,
            old_price_try     REAL,
            discount_pct      INTEGER DEFAULT 0,
            platform          TEXT,
            ps_store_url      TEXT,
            region            TEXT    NOT NULL,
            sort_order        INTEGER DEFAULT 0,
            is_active         INTEGER DEFAULT 1,
            is_free           INTEGER DEFAULT 0,
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_game_editions_parent ON game_editions(parent_product_id)",
        "ALTER TABLE products ADD COLUMN task_type TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN old_price REAL",
        "ALTER TABLE products ADD COLUMN original_id TEXT",
        "ALTER TABLE products ADD COLUMN genre TEXT",
        "ALTER TABLE products ADD COLUMN requires_ps_plus INTEGER DEFAULT 0",
        # Data migrations: populate task_type for legacy products that have none set
        "UPDATE products SET task_type = 'preorders' WHERE (task_type IS NULL OR task_type = '') AND is_preorder = 1",
        "UPDATE products SET task_type = 'sales' WHERE (task_type IS NULL OR task_type = '') AND discount_pct > 0",
        "UPDATE products SET task_type = 'new_games' WHERE (task_type IS NULL OR task_type = '') AND product_type = 'game'",
        # Normalise legacy platform values
        "UPDATE products SET platform='PS4, PS5' WHERE platform IN ('PS5/PS4','PS4/PS5')",
        "UPDATE products SET platform='PS4'      WHERE platform IN ('PS4\u2122')",
        "UPDATE products SET platform=NULL       WHERE platform IN ('PS','PS3\u2122','')",
        """CREATE TABLE IF NOT EXISTS parser_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            region           TEXT      NOT NULL,
            task_type        TEXT      NOT NULL,
            started_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at      TIMESTAMP,
            status           TEXT      DEFAULT 'running',
            products_added   INTEGER   DEFAULT 0,
            products_updated INTEGER   DEFAULT 0,
            errors_count     INTEGER   DEFAULT 0,
            details          TEXT
        )""",
    ]
    for sql in migrations:
        try:
            await conn.execute(sql)
            await conn.commit()
        except Exception:
            pass  # Column/table already exists

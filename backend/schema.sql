-- =============================================================
--  TG-Shop  |  Database Schema (SQLite)
-- =============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------
--  Categories
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    slug        TEXT    NOT NULL UNIQUE,
    icon        TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------
--  Products
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    title           TEXT    NOT NULL,
    description     TEXT,
    image_url       TEXT,
    price_uah       REAL,
    price_try       REAL,
    price_inr       REAL,
    price_pln       REAL,
    price_byn       INTEGER,   -- manual override for BYN price (UA region)
    price_byn_tr    INTEGER,   -- manual override for BYN price (TR region)
    original_id     TEXT    UNIQUE,     -- PS Store product ID
    platform        TEXT    DEFAULT 'PS',
    rating          REAL    DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    is_featured     INTEGER DEFAULT 0,
    discount_pct    REAL    DEFAULT 0,
    discount_until  DATETIME,
    region          TEXT    DEFAULT 'UA',
    has_editions    INTEGER DEFAULT 0,
    task_type       TEXT    DEFAULT '',   -- 'new_games' | 'sales' | 'preorders' | ''
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_editions (
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
);

CREATE INDEX IF NOT EXISTS idx_game_editions_parent ON game_editions(parent_product_id);

CREATE TABLE IF NOT EXISTS parser_log (
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
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active   ON products(is_active);

-- -----------------------------------------------------------
--  Users (Telegram)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,   -- Telegram user_id
    username        TEXT,
    first_name      TEXT,
    last_name       TEXT,
    language_code   TEXT    DEFAULT 'uk',
    is_premium      INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------
--  Orders
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    status          TEXT    NOT NULL DEFAULT 'pending',
                    -- pending | paid | processing | completed | cancelled
    total_stars     INTEGER NOT NULL DEFAULT 0,
    telegram_payment_charge_id  TEXT UNIQUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- -----------------------------------------------------------
--  Order Items
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    quantity    INTEGER NOT NULL DEFAULT 1,
    price_paid  REAL    NOT NULL,
    region      TEXT    NOT NULL DEFAULT 'UA'
);

CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

-- -----------------------------------------------------------
--  Cart (server-side, keyed by Telegram user_id)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS cart_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity    INTEGER NOT NULL DEFAULT 1,
    region      TEXT    NOT NULL DEFAULT 'UA',
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id, region)
);

-- -----------------------------------------------------------
--  Favourites
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS favourites (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, product_id)
);

-- -----------------------------------------------------------
--  Price snapshots (populated by parser)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    region      TEXT    NOT NULL,
    price       REAL    NOT NULL,
    currency    TEXT    NOT NULL,
    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_product ON price_snapshots(product_id, region);

-- Rocky Top Outfitters pipeline schema (SQLite dialect)
-- Layers: RAW -> REFERENCE -> TEAM-CREATED -> CLEAN/ANALYTICS
-- Created by:  uv run python -m src.init_db

-- ========================= LAYER 1: RAW =========================
-- Orders exactly as received. Everything is TEXT: we do not trust the source
-- yet. Both possible product columns plus the migration flag are kept so the
-- raw table can hold every phase of the feed unchanged.
CREATE TABLE IF NOT EXISTS raw_orders (
    raw_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file       TEXT NOT NULL,        -- orders_2026-08-03.csv
    ingested_at       TEXT NOT NULL,        -- UTC ISO-8601
    order_id          TEXT,
    order_date        TEXT,
    store_id          TEXT,
    product_id        TEXT,                 -- legacy IDs (P####)
    new_product_id    TEXT,                 -- new-system IDs (NP####)
    product_id_source TEXT,                 -- 'new_system' flag (2026-07-31+)
    quantity          TEXT,
    unit_price        TEXT,
    discount_pct      TEXT,
    sales_channel     TEXT,
    loyalty_member    TEXT
);

-- ====================== LAYER 2: REFERENCE ======================
-- Pulled from the UTK MySQL databases (Step 6).
CREATE TABLE IF NOT EXISTS stores (
    store_id     TEXT PRIMARY KEY,
    store_name   TEXT,
    city         TEXT,
    state        TEXT,
    latitude     REAL,                      -- weather API input
    longitude    REAL,
    region       TEXT,
    store_type   TEXT,
    opened_date  TEXT
);

CREATE TABLE IF NOT EXISTS products (       -- legacy catalog
    product_id   TEXT PRIMARY KEY,
    product_name TEXT,
    category     TEXT,
    subcategory  TEXT,
    brand        TEXT,
    base_price   REAL,
    margin_rate  REAL,
    launch_date  TEXT,
    active       INTEGER
);

CREATE TABLE IF NOT EXISTS new_products (   -- post-migration catalog
    new_product_id TEXT PRIMARY KEY,
    item_name    TEXT,
    department   TEXT,
    class        TEXT,
    brand_name   TEXT,
    msrp         REAL,
    gross_margin REAL,
    launch_date  TEXT,
    active       INTEGER
);

-- ==================== LAYER 3: TEAM-CREATED =====================
CREATE TABLE IF NOT EXISTS ingestion_log (
    run_id               TEXT PRIMARY KEY,
    run_timestamp        TEXT NOT NULL,
    source_url           TEXT NOT NULL,
    source_date_expected TEXT,
    source_date_found    TEXT,
    status               TEXT NOT NULL,     -- success|stale|empty|missing|failed
    rows_loaded          INTEGER,
    file_hash            TEXT,
    error_message        TEXT
);

CREATE TABLE IF NOT EXISTS product_crosswalk (
    product_id       TEXT,
    new_product_id   TEXT,
    match_status     TEXT,   -- matched|possible_match|discontinued|replacement|unresolved
    match_confidence TEXT,   -- high|medium|low
    match_method     TEXT,   -- exact|name_similarity|category_brand_price|manual
    notes            TEXT,
    PRIMARY KEY (product_id, new_product_id)
);

CREATE TABLE IF NOT EXISTS weather_daily (
    weather_date       TEXT,
    store_id           TEXT REFERENCES stores(store_id),
    temperature_2m_max REAL,
    temperature_2m_min REAL,
    precipitation_sum  REAL,
    weather_code       INTEGER,
    weather_source     TEXT,
    PRIMARY KEY (weather_date, store_id)
);

-- Rows dropped/quarantined during cleaning (never silently deleted).
CREATE TABLE IF NOT EXISTS rejected_rows (
    source_file  TEXT,
    reason       TEXT,
    order_id     TEXT,
    raw_json     TEXT
);

-- ================= LAYER 4: CLEAN / ANALYTICS ===================
CREATE TABLE IF NOT EXISTS clean_orders (
    order_id          TEXT,
    order_date        TEXT NOT NULL,
    store_id          TEXT REFERENCES stores(store_id),
    product_key       TEXT,                 -- normalized to new_product_id when resolvable
    legacy_product_id TEXT,
    is_new_system     INTEGER,              -- 1 if the value came from the new catalog
    quantity          INTEGER,
    unit_price        REAL,
    discount_pct      REAL,
    line_revenue      REAL,                 -- quantity * unit_price
    sales_channel     TEXT,
    loyalty_member    INTEGER,
    source_file       TEXT,
    UNIQUE (order_id, order_date, store_id, product_key)
);

-- Analytics-ready table (grain: one row per date x store x category).
-- Revenue is reported both net and gross because unit_price is already the
-- post-discount price (verified: unit_price = base_price * (1 - discount_pct/100)):
--   net_revenue    = quantity * unit_price           (what customers actually paid)
--   gross_revenue  = quantity * unit_price / (1 - discount_pct/100)  (list price)
--   discount_given = gross_revenue - net_revenue
CREATE TABLE IF NOT EXISTS daily_sales (
    order_date        TEXT,
    store_id          TEXT,
    category          TEXT,           -- new-system department (UNKNOWN only for true orphans)
    category_source   TEXT,           -- new_system | legacy_recovered | unknown
    units_sold        INTEGER,
    net_revenue       REAL,
    gross_revenue     REAL,
    discount_given    REAL,
    temp_max          REAL,
    temp_min          REAL,
    precipitation_sum REAL,
    weather_code      INTEGER,
    PRIMARY KEY (order_date, store_id, category, category_source)
);

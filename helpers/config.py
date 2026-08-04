"""
Central configuration for the Rocky Top Outfitters data pipeline.

Only NON-secret settings live here (paths, URLs, table/column names).
Database credentials are read separately from credentials.json (git-ignored)
by helpers/db.py -- never put usernames or passwords in this file.
"""

from pathlib import Path

# --- Project paths --------------------------------------------------------
# Resolve everything relative to the repo root so scripts work no matter which
# directory they are launched from.
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
WEATHER_CACHE_DIR = DATA_DIR / "weather_cache"

SQLITE_PATH = ROOT_DIR / "rocky_top.db"
INGESTION_LOG_CSV = DATA_DIR / "ingestion_log.csv"
DATA_QUALITY_LOG_CSV = DATA_DIR / "data_quality_log.csv"

CREDENTIALS_PATH = ROOT_DIR / "credentials.json"  # git-ignored

# --- Source feed ----------------------------------------------------------
# The canonical source is this public GitHub raw file. tiny.utk.edu/RToutfitters
# /daily/orders.csv is just a short link that redirects here; we use the direct
# raw URL so it is guaranteed reachable from GitHub Actions.
ORDERS_URL = ("https://raw.githubusercontent.com/AdamSpannbauer/"
              "su26-bzan545-current-orders/refs/heads/master/orders.csv")

# --- Orders schema knowledge (used from Step 3 onward) --------------------
# The daily file uses one of two product-identifier columns depending on the
# migration phase. We never trust the header alone.
LEGACY_PRODUCT_COL = "product_id"        # values like "P1055"
NEW_PRODUCT_COL = "new_product_id"       # values like "NP5047"
PRODUCT_SOURCE_COL = "product_id_source" # flag added 2026-07-31+ ("new_system")

# --- UTK databases --------------------------------------------------------
# The team DB is derived per-user as "<username>_<TEAM_DB_SUFFIX>", where the
# username comes from the git-ignored credentials.json. This way no personal
# NetID is committed to the repo. Only the generic course suffix lives here.
# (You can still override the full name with "team_db" in credentials.json.)
TEAM_DB_SUFFIX = "bzan545"

# --- Reference tables (pulled from the UTK MySQL databases) ----------------
REFERENCE_TABLES = ["stores", "products", "new_products"]

# --- Ingestion-log status vocabulary --------------------------------------
STATUS_SUCCESS = "success"
STATUS_STALE = "stale"      # file's internal date != expected date
STATUS_EMPTY = "empty"      # header present but zero data rows
STATUS_MISSING = "missing"  # no file for the expected date
STATUS_FAILED = "failed"    # download / read error

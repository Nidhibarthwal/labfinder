# app/config.py
"""
Central config. Loads .env once, and loads the watched-tables list from
config/watched_tables.json -- edit that JSON file and restart the server
to change which tables broadcast realtime updates. No code changes needed.
"""

import json
import os
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
WATCHED_TABLES_PATH = BASE_DIR / "config" / "watched_tables.json"

# --- Database ---
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = quote(os.environ["DB_PASSWORD"], safe="")
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- CORS ---
_raw_origins = os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000")
FRONTEND_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

# --- SSE / subscriber tuning ---
# NOTIFY_CHANNEL is the single Postgres channel every watched table's
# trigger publishes to (and the one FastAPI LISTENs on). Renamed to
# 'realtime_channel' since it now covers multiple tables, not just
# inventory. Override via .env if you want a different name.
NOTIFY_CHANNEL = os.environ.get("NOTIFY_CHANNEL", "realtime_channel")
MAX_SUBSCRIBERS_PER_TENANT = int(os.environ.get("MAX_SUBSCRIBERS_PER_TENANT", "2000"))
QUEUE_MAXSIZE = int(os.environ.get("QUEUE_MAXSIZE", "100"))
HEARTBEAT_SECONDS = int(os.environ.get("HEARTBEAT_SECONDS", "15"))
TOKEN_CACHE_TTL_SECONDS = int(os.environ.get("TOKEN_CACHE_TTL_SECONDS", "60"))


def load_watched_tables() -> list[str]:
    """Reads config/watched_tables.json. Add/remove table names there and
    restart the server -- no code edits needed."""
    if not WATCHED_TABLES_PATH.exists():
        raise FileNotFoundError(
            f"watched_tables.json not found at {WATCHED_TABLES_PATH}. "
            "Create it with: {\"watched_tables\": [\"your_table\"]}"
        )
    with open(WATCHED_TABLES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    tables = data.get("watched_tables", [])
    if not tables:
        raise ValueError("watched_tables.json has no tables listed under 'watched_tables'.")
    return tables
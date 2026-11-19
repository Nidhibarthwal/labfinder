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
# Default to LabFinder database settings (from settings_local.py) if not set in environment
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = quote(os.environ.get("DB_PASSWORD", "proot"), safe="")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "labfinder")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# --- CORS ---
_default_origins = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000,https://labfinder.stagemyapp.com"
_raw_origins = os.environ.get("FRONTEND_ORIGINS", _default_origins)
FRONTEND_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

# --- SSE / subscriber tuning ---
NOTIFY_CHANNEL = os.environ.get("NOTIFY_CHANNEL", "labfinder_realtime")
MAX_SUBSCRIBERS_PER_ROOM = int(os.environ.get("MAX_SUBSCRIBERS_PER_ROOM", "5000"))
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
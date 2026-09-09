from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import get_backend_dir, get_settings

DB_PATH = get_backend_dir() / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trade_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    leg_key TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('long', 'short')),
    quote_type TEXT NOT NULL DEFAULT 'mid' CHECK(quote_type IN ('mid', 'opponent', 'limit')),
    qty INTEGER NOT NULL DEFAULT 1,
    strike REAL NOT NULL,
    month TEXT NOT NULL,
    is_call INTEGER NOT NULL,
    iv REAL,
    delta REAL NOT NULL DEFAULT 0,
    gamma REAL NOT NULL DEFAULT 0,
    theta REAL NOT NULL DEFAULT 0,
    vega REAL NOT NULL DEFAULT 0,
    bid REAL,
    ask REAL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trade_legs_sort ON trade_legs(sort_order);
"""


def get_db_path() -> Path:
    settings = get_settings()
    if settings.database_url.startswith("sqlite:///"):
        rel = settings.database_url.replace("sqlite:///", "", 1).lstrip("./")
        return get_backend_dir() / rel
    return DB_PATH


def connect() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()

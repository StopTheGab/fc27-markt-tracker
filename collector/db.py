"""SQLite storage. All timestamps are stored as ISO 8601 UTC strings ('2026-10-05T08:15:00Z')."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,             -- watchlist entry as JSON
    active INTEGER NOT NULL DEFAULT 1,
    price_min INTEGER, price_max INTEGER,
    available INTEGER,
    history_imported_at TEXT
);
CREATE TABLE IF NOT EXISTS prices (
    card_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    price INTEGER,
    origin TEXT NOT NULL DEFAULT 'live',   -- live | history
    source TEXT,
    source_updated_at TEXT,
    PRIMARY KEY (card_id, ts)
);
CREATE INDEX IF NOT EXISTS idx_prices_ts ON prices(ts);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    ok INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    cards INTEGER, prices INTEGER,
    errors TEXT
);
CREATE TABLE IF NOT EXISTS signal_state (
    card_id TEXT PRIMARY KEY,
    type TEXT,                 -- buy | sell | NULL
    since TEXT,
    last_cleared_at TEXT,
    last_cleared_type TEXT
);
CREATE TABLE IF NOT EXISTS tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    buy_price INTEGER NOT NULL,
    avg_7d INTEGER NOT NULL,
    expected_profit INTEGER NOT NULL,
    confidence TEXT,
    reasons TEXT,
    closed_at TEXT,
    close_price INTEGER,
    realized_profit INTEGER,
    outcome TEXT               -- hit | miss | NULL (open)
);
CREATE TABLE IF NOT EXISTS mail_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,        -- signal | hourly | test
    sent_at TEXT NOT NULL,
    subject TEXT,
    ok INTEGER NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def kv_get(con: sqlite3.Connection, key: str, default=None):
    row = con.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def kv_set(con: sqlite3.Connection, key: str, value) -> None:
    con.execute("INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)))
    con.commit()


def sync_watchlist(con: sqlite3.Connection, cards: list[dict]) -> None:
    ids = []
    for c in cards:
        cid = c.get("id")
        if not cid:
            continue
        ids.append(cid)
        con.execute(
            "INSERT INTO cards(card_id,data,active) VALUES(?,?,1) "
            "ON CONFLICT(card_id) DO UPDATE SET data=excluded.data, active=1",
            (cid, json.dumps(c, ensure_ascii=False)),
        )
    if ids:
        marks = ",".join("?" * len(ids))
        con.execute(f"UPDATE cards SET active=0 WHERE card_id NOT IN ({marks})", ids)
    con.commit()


def active_cards(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("SELECT * FROM cards WHERE active=1").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        d["_price_min"] = r["price_min"]
        d["_price_max"] = r["price_max"]
        d["_available"] = None if r["available"] is None else bool(r["available"])
        d["_history_imported_at"] = r["history_imported_at"]
        out.append(d)
    return out


def insert_price(con, card_id: str, ts: str, price: int | None, origin: str, source: str | None,
                 source_updated_at: str | None = None) -> bool:
    cur = con.execute(
        "INSERT OR IGNORE INTO prices(card_id,ts,price,origin,source,source_updated_at) VALUES(?,?,?,?,?,?)",
        (card_id, ts, price, origin, source, source_updated_at),
    )
    return cur.rowcount > 0


def price_series(con, card_id: str, since: str) -> list[tuple[datetime, int]]:
    rows = con.execute(
        "SELECT ts, price FROM prices WHERE card_id=? AND ts>=? AND price IS NOT NULL "
        "AND origin != 'suspect' ORDER BY ts",
        (card_id, since),
    ).fetchall()
    return [(parse(r["ts"]), int(r["price"])) for r in rows]


def classify_price(con, card_id: str, price: int, max_dev: float | None = None) -> str:
    """'live' or 'suspect': a point > max_dev away from the median of the last 8 valid points is suspect
    (source glitch, e.g. Bellingham 167k -> 1.5k). A suspect point is promoted when the next one confirms it."""
    rows = con.execute("SELECT ts, price, origin FROM prices WHERE card_id=? AND price IS NOT NULL "
                       "ORDER BY ts DESC LIMIT 9", (card_id,)).fetchall()
    valid = [r["price"] for r in rows if r["origin"] != "suspect"][:8]
    if len(valid) < 3:
        return "live"
    valid.sort()
    med = valid[len(valid) // 2]
    if max_dev is None:  # expensive cards rarely jump 30 %+ in 15 min; cheap ones move by whole price steps
        max_dev = 0.3 if med >= 100_000 else 0.5
    if abs(price - med) <= med * max_dev:
        return "live"
    last = rows[0] if rows else None
    if last is not None and last["origin"] == "suspect" and abs(price - last["price"]) <= last["price"] * 0.1:
        # two consecutive points agree -> real move; promote the earlier one as well
        con.execute("UPDATE prices SET origin='live' WHERE card_id=? AND ts=?", (card_id, last["ts"]))
        return "live"
    return "suspect"


def latest_assessment(con) -> dict | None:
    r = con.execute("SELECT * FROM assessments ORDER BY id DESC LIMIT 1").fetchone()
    return dict(r) if r else None

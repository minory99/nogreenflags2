import sqlite3
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    name            TEXT,
    age             INTEGER,
    gender          TEXT,
    looking_for     TEXT,
    bio             TEXT,
    photo_file_id   TEXT,
    custom_flaws    TEXT,
    custom_tolerance TEXT,
    city            TEXT,
    username        TEXT,
    is_profile_complete INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_flaws (
    user_id INTEGER,
    flaw_id TEXT,
    PRIMARY KEY (user_id, flaw_id)
);

CREATE TABLE IF NOT EXISTS user_tolerance (
    user_id INTEGER,
    flaw_id TEXT,
    PRIMARY KEY (user_id, flaw_id)
);

CREATE TABLE IF NOT EXISTS actions (
    from_id     INTEGER,
    to_id       INTEGER,
    action      TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS matches (
    user_a      INTEGER,
    user_b      INTEGER,
    score       REAL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_a, user_b)
);

CREATE TABLE IF NOT EXISTS reports (
    from_id     INTEGER,
    to_id       INTEGER,
    reason      TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _migrate_columns():
    with get_conn() as conn:
        existing_users_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "username" not in existing_users_cols:
            conn.execute("ALTER TABLE users ADD COLUMN username TEXT")

        existing_reports_cols = {row["name"] for row in conn.execute("PRAGMA table_info(reports)")}
        if "reason" not in existing_reports_cols:
            conn.execute("ALTER TABLE reports ADD COLUMN reason TEXT")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    _migrate_columns()


def upsert_user(user_id: int, **fields):
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if exists:
            if fields:
                set_clause = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(
                    f"UPDATE users SET {set_clause} WHERE user_id = ?",
                    (*fields.values(), user_id),
                )
        else:
            cols = ["user_id"] + list(fields.keys())
            placeholders = ", ".join("?" for _ in cols)
            conn.execute(
                f"INSERT INTO users ({', '.join(cols)}) VALUES ({placeholders})",
                (user_id, *fields.values()),
            )


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def mark_profile_complete(user_id: int):
    upsert_user(user_id, is_profile_complete=1)


def set_user_flaws(user_id: int, flaw_ids: list[str]):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_flaws WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO user_flaws (user_id, flaw_id) VALUES (?, ?)",
            [(user_id, f) for f in flaw_ids],
        )


def set_user_tolerance(user_id: int, flaw_ids: list[str]):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_tolerance WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO user_tolerance (user_id, flaw_id) VALUES (?, ?)",
            [(user_id, f) for f in flaw_ids],
        )


def get_user_flaws(user_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT flaw_id FROM user_flaws WHERE user_id = ?", (user_id,)).fetchall()
        return [r["flaw_id"] for r in rows]


def get_user_tolerance(user_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT flaw_id FROM user_tolerance WHERE user_id = ?", (user_id,)).fetchall()
        return [r["flaw_id"] for r in rows]


def record_action(from_id: int, to_id: int, action: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO actions (from_id, to_id, action) VALUES (?, ?, ?)",
            (from_id, to_id, action),
        )


def has_mutual_like(from_id: int, to_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM actions WHERE from_id = ? AND to_id = ? AND action = 'like'",
            (to_id, from_id),
        ).fetchone()
        return row is not None


def create_match(user_a: int, user_b: int, score: float):
    a, b = sorted((user_a, user_b))
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO matches (user_a, user_b, score) VALUES (?, ?, ?)",
            (a, b, score),
        )


def get_seen_ids(user_id: int) -> set[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT to_id FROM actions WHERE from_id = ?", (user_id,)).fetchall()
        return {r["to_id"] for r in rows}


def get_candidates(user_id: int) -> list[sqlite3.Row]:
    seen = get_seen_ids(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM users
               WHERE user_id != ? AND is_profile_complete = 1 AND is_active = 1""",
            (user_id,),
        ).fetchall()
    return [r for r in rows if r["user_id"] not in seen]


def get_matches_for_user(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM matches WHERE user_a = ? OR user_b = ?
               ORDER BY created_at DESC""",
            (user_id, user_id),
        ).fetchall()
    return rows


def delete_match(user_a: int, user_b: int):
    a, b = sorted((user_a, user_b))
    with get_conn() as conn:
        conn.execute("DELETE FROM matches WHERE user_a = ? AND user_b = ?", (a, b))
        # Стираем лайки друг друга — иначе get_candidates() будет считать их
        # "уже просмотренными" и разматченный человек никогда больше не попадётся в поиске.
        conn.execute(
            "DELETE FROM actions WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)",
            (user_a, user_b, user_b, user_a),
        )


def create_report(from_id: int, to_id: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (from_id, to_id, reason) VALUES (?, ?, ?)", (from_id, to_id, reason)
        )

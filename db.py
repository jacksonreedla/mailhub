"""Mailhub SQLite schema and connection helpers."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    display_name TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    uid INTEGER NOT NULL,
    folder TEXT NOT NULL DEFAULT 'INBOX',
    message_id TEXT DEFAULT '',
    thread_key TEXT DEFAULT '',
    from_name TEXT DEFAULT '',
    from_email TEXT DEFAULT '',
    to_json TEXT DEFAULT '[]',
    date_utc TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body_text TEXT DEFAULT '',
    body_html TEXT DEFAULT '',
    snippet TEXT DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (account_id, folder, uid)
);

CREATE INDEX IF NOT EXISTS idx_messages_date ON messages (date_utc DESC);
CREATE INDEX IF NOT EXISTS idx_messages_account ON messages (account_id);

CREATE TABLE IF NOT EXISTS sync_state (
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    folder TEXT NOT NULL,
    uidvalidity INTEGER NOT NULL DEFAULT 0,
    last_uid INTEGER NOT NULL DEFAULT 0,
    last_sync_utc TEXT DEFAULT '',
    last_error TEXT DEFAULT '',
    PRIMARY KEY (account_id, folder)
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    position INTEGER NOT NULL DEFAULT 0,
    field TEXT NOT NULL,
    pattern TEXT NOT NULL,
    lane TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    subject, body_text, from_email,
    content='messages', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts (rowid, subject, body_text, from_email)
    VALUES (new.id, new.subject, new.body_text, new.from_email);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, subject, body_text, from_email)
    VALUES ('delete', old.id, old.subject, old.body_text, old.from_email);
END;

CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, subject, body_text, from_email)
    VALUES ('delete', old.id, old.subject, old.body_text, old.from_email);
    INSERT INTO messages_fts (rowid, subject, body_text, from_email)
    VALUES (new.id, new.subject, new.body_text, new.from_email);
END;
"""


def connect(path):
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(messages)")}
    if "lane" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN lane TEXT DEFAULT ''")
    if "is_bulk" not in cols:
        conn.execute("ALTER TABLE messages ADD COLUMN is_bulk INTEGER DEFAULT 0")


def init_db(conn):
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()

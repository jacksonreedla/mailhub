import sqlite3

import db


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_fresh_db_has_lane_and_rules(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    db.init_db(conn)
    assert {"lane", "is_bulk"} <= _cols(conn, "messages")
    assert {"id", "position", "field", "pattern", "lane", "enabled"} <= _cols(
        conn, "rules")


def test_existing_db_is_migrated(tmp_path):
    # build a phase-1 style DB lacking the new columns
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, account_id INTEGER,"
        " uid INTEGER, folder TEXT, message_id TEXT, thread_key TEXT,"
        " from_name TEXT, from_email TEXT, to_json TEXT, date_utc TEXT,"
        " subject TEXT, body_text TEXT, body_html TEXT, snippet TEXT,"
        " is_read INTEGER, created_at TEXT)")
    raw.commit()
    raw.close()
    conn = db.connect(path)
    db.init_db(conn)
    assert {"lane", "is_bulk"} <= _cols(conn, "messages")

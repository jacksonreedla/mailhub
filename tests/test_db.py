import db


def table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')"
    ).fetchall()
    return {r["name"] for r in rows}


def test_init_db_creates_schema(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    names = table_names(conn)
    for t in ("accounts", "messages", "sync_state", "messages_fts"):
        assert t in names, f"missing {t}"


def test_init_db_idempotent(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    db.init_db(conn)  # must not raise


def _insert_message(conn, uid=1, subject="hello world"):
    conn.execute(
        "INSERT INTO accounts (email, provider) VALUES ('a@x.com', 'gmail')"
    )
    conn.execute(
        "INSERT INTO messages (account_id, uid, folder, subject, body_text,"
        " from_email, date_utc) VALUES (1, ?, 'INBOX', ?, 'body text',"
        " 'a@x.com', '2026-08-05T00:00:00Z')",
        (uid, subject),
    )
    conn.commit()


def test_fts_tracks_insert_and_delete(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _insert_message(conn, subject="unique zanzibar subject")
    hits = conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'zanzibar'"
    ).fetchall()
    assert len(hits) == 1

    conn.execute("DELETE FROM messages")
    conn.commit()
    hits = conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'zanzibar'"
    ).fetchall()
    assert hits == []


def test_uid_unique_per_account_folder(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    _insert_message(conn, uid=7)
    before = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    conn.execute(
        "INSERT OR IGNORE INTO messages (account_id, uid, folder, subject,"
        " from_email, date_utc) VALUES (1, 7, 'INBOX', 'dupe', 'a@x.com', '')"
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    assert before == after == 1

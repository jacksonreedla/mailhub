"""Message persistence and query API on top of db.py's schema."""

LIST_COLUMNS = ("m.id, m.account_id, a.email AS account_email, m.uid,"
                " m.folder, m.message_id, m.thread_key, m.from_name,"
                " m.from_email, m.date_utc, m.subject, m.snippet, m.is_read")


def upsert_account(conn, email, provider, display_name=""):
    conn.execute(
        "INSERT INTO accounts (email, provider, display_name) VALUES (?,?,?)"
        " ON CONFLICT(email) DO UPDATE SET provider=excluded.provider",
        (email, provider, display_name),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM accounts WHERE email=?", (email,)).fetchone()
    return row["id"]


def upsert_message(conn, account_id, folder, uid, parsed):
    cur = conn.execute(
        "INSERT OR IGNORE INTO messages (account_id, folder, uid, message_id,"
        " thread_key, from_name, from_email, to_json, date_utc, subject,"
        " body_text, body_html, snippet)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            account_id, folder, uid,
            parsed["message_id"], parsed["thread_key"], parsed["from_name"],
            parsed["from_email"], parsed["to_json"], parsed["date_utc"],
            parsed["subject"], parsed["body_text"], parsed["body_html"],
            parsed["snippet"],
        ),
    )
    conn.commit()
    if cur.lastrowid and cur.rowcount:
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM messages WHERE account_id=? AND folder=? AND uid=?",
        (account_id, folder, uid),
    ).fetchone()
    return row["id"]


def list_messages(conn, account_id=None, limit=100, offset=0):
    sql = (f"SELECT {LIST_COLUMNS} FROM messages m"
           " JOIN accounts a ON a.id = m.account_id")
    args = []
    if account_id is not None:
        sql += " WHERE m.account_id = ?"
        args.append(account_id)
    sql += " ORDER BY m.date_utc DESC, m.id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def _fts_query(query):
    """Quote each term so user input can't hit FTS5 operator syntax."""
    terms = [t.replace('"', "") for t in query.split()]
    return " ".join(f'"{t}"' for t in terms if t)


def search_messages(conn, query, limit=100):
    fts = _fts_query(query)
    if not fts:
        return []
    sql = (f"SELECT {LIST_COLUMNS} FROM messages_fts f"
           " JOIN messages m ON m.id = f.rowid"
           " JOIN accounts a ON a.id = m.account_id"
           " WHERE messages_fts MATCH ?"
           " ORDER BY m.date_utc DESC, m.id DESC LIMIT ?")
    return [dict(r) for r in conn.execute(sql, (fts, limit)).fetchall()]


def get_message(conn, message_id):
    row = conn.execute(
        f"SELECT {LIST_COLUMNS}, m.to_json, m.body_text, m.body_html"
        " FROM messages m JOIN accounts a ON a.id = m.account_id"
        " WHERE m.id = ?",
        (message_id,),
    ).fetchone()
    return dict(row) if row else None


def mark_read(conn, message_id, read=True):
    conn.execute("UPDATE messages SET is_read=? WHERE id=?",
                 (1 if read else 0, message_id))
    conn.commit()


def get_sync_state(conn, account_id, folder):
    row = conn.execute(
        "SELECT uidvalidity, last_uid FROM sync_state"
        " WHERE account_id=? AND folder=?",
        (account_id, folder),
    ).fetchone()
    return (row["uidvalidity"], row["last_uid"]) if row else None


def set_sync_state(conn, account_id, folder, uidvalidity, last_uid):
    conn.execute(
        "INSERT INTO sync_state (account_id, folder, uidvalidity, last_uid,"
        " last_sync_utc) VALUES (?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        " ON CONFLICT(account_id, folder) DO UPDATE SET"
        " uidvalidity=excluded.uidvalidity, last_uid=excluded.last_uid,"
        " last_sync_utc=excluded.last_sync_utc",
        (account_id, folder, uidvalidity, last_uid),
    )
    conn.commit()


def delete_account_messages(conn, account_id, folder):
    conn.execute("DELETE FROM messages WHERE account_id=? AND folder=?",
                 (account_id, folder))
    conn.commit()

"""Mailhub — local unified email triage dashboard.

Run: venv/bin/python app.py  →  http://127.0.0.1:8770
"""

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import accounts as accounts_mod
import db
import store
from sync import SyncDaemon

DEFAULT_DB = Path.home() / ".mailhub" / "mailhub.db"


def create_app(db_path=None, daemon=None):
    app = Flask(__name__, static_folder="static")
    app.config["DB_PATH"] = str(db_path or os.environ.get("MAILHUB_DB",
                                                          DEFAULT_DB))
    app.config["DAEMON"] = daemon

    def conn():
        if "db" not in app.extensions:
            c = db.connect(app.config["DB_PATH"])
            db.init_db(c)
            app.extensions["db"] = c
        return app.extensions["db"]

    @app.get("/")
    def home():
        return send_from_directory("static", "index.html")

    @app.get("/api/messages")
    def list_messages():
        q = request.args.get("q", "").strip()
        account = request.args.get("account", type=int)
        limit = min(request.args.get("limit", 100, type=int), 500)
        offset = request.args.get("offset", 0, type=int)
        if q:
            msgs = store.search_messages(conn(), q, limit=limit)
            if account is not None:
                msgs = [m for m in msgs if m["account_id"] == account]
        else:
            msgs = store.list_messages(conn(), account_id=account,
                                       limit=limit, offset=offset)
        return jsonify({"messages": msgs})

    @app.get("/api/messages/<int:mid>")
    def get_message(mid):
        m = store.get_message(conn(), mid)
        if m is None:
            return jsonify({"error": "no such message"}), 404
        return jsonify(m)

    @app.post("/api/messages/<int:mid>/read")
    def mark_read(mid):
        if store.get_message(conn(), mid) is None:
            return jsonify({"error": "no such message"}), 404
        body = request.get_json(silent=True) or {}
        store.mark_read(conn(), mid, bool(body.get("read", True)))
        return jsonify({"ok": True})

    @app.get("/api/accounts")
    def list_accounts():
        rows = conn().execute(
            "SELECT a.id, a.email, a.provider, a.display_name,"
            " COUNT(m.id) AS message_count,"
            " SUM(CASE WHEN m.is_read=0 THEN 1 ELSE 0 END) AS unread_count"
            " FROM accounts a LEFT JOIN messages m ON m.account_id = a.id"
            " GROUP BY a.id ORDER BY a.email"
        ).fetchall()
        return jsonify({"accounts": [dict(r) for r in rows]})

    @app.post("/api/sync")
    def trigger_sync():
        d = app.config["DAEMON"]
        if d is None:
            return jsonify({"error": "sync daemon not running"}), 503
        d.trigger()
        return jsonify({"ok": True})

    @app.get("/api/status")
    def status():
        d = app.config["DAEMON"]
        if d is None:
            return jsonify({"daemon": "off", "accounts": {}})
        return jsonify({
            "daemon": "alive" if d.is_alive() else "dead",
            "accounts": d.status,
        })

    return app


def main():
    accounts_mod.ensure_config_dir()
    accts = accounts_mod.load_accounts()
    daemon = None
    if accts and not os.environ.get("MAILHUB_NO_SYNC"):
        daemon = SyncDaemon(str(DEFAULT_DB), accts)
        daemon.start()
    elif not accts:
        print(f"No accounts configured — create {accounts_mod.CREDENTIALS_PATH}"
              " (see credentials.json.example). Serving existing data only.")
    app = create_app(daemon=daemon)
    app.run(host="127.0.0.1", port=8770)


if __name__ == "__main__":
    main()

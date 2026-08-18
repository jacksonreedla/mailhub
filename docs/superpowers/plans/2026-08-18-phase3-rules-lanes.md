# Phase 3: Rules + Lanes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every message gets a lane (people / newsletters / receipts / notifications) from ordered user rules + built-in heuristics; the UI filters by lane and lets the user manage rules.

**Architecture:** New `rules.py` module is a pure classifier: `classify(msg, user_rules) -> lane`. User rules (SQLite `rules` table, ordered, substring matches) run first; deterministic heuristics (receipts → notifications → newsletters → people fallback) decide the rest. Classification happens at sync-ingest time and is stored on `messages.lane`; any rule change triggers a cheap full reclassify. The 2026-08-18 inbox survey (51k messages) informed the heuristic domain/localpart lists.

**Tech Stack:** Python 3.12, Flask, SQLite (existing venv; no new dependencies).

## Global Constraints

- Lanes are exactly: `people`, `newsletters`, `receipts`, `notifications` (lowercase in DB; spec's display names: People / Newsletters / Receipts / Notifications).
- The app NEVER writes to providers — lanes/rules are local-only state.
- All work TDD; run tests with `venv/bin/python -m pytest -q` from `~/mailhub`.
- Existing 35-test suite must stay green.
- Do NOT restyle the SPA (Telegraph Exchange skin is a separate approved-style-tile track); new UI uses the existing plain styles.
- Work on branch `phase-3-lanes`.

## File Structure

- `db.py` — add `lane`/`is_bulk` columns (migration for existing DBs) + `rules` table.
- `mailparse.py` — parse bulk-mail headers into `is_bulk`.
- `rules.py` (new) — pure classification: heuristics + user-rule matching.
- `store.py` — rules CRUD, lane persistence, lane filtering/counts, reclassify.
- `sync.py` — classify each message at ingest.
- `app.py` — `lane` filter param, `/api/lanes`, `/api/rules` endpoints.
- `static/index.html` — lane chips + rules panel.
- `tests/test_rules.py`, `tests/test_lanes_api.py` (new); small additions to existing test files' fixtures only if needed.

---

### Task 1: Schema — lane/is_bulk columns, rules table, migration

**Files:**
- Modify: `db.py`
- Test: `tests/test_db_migration.py` (create)

**Interfaces:**
- Produces: `messages.lane TEXT DEFAULT ''`, `messages.is_bulk INTEGER DEFAULT 0`, table `rules (id, position, field, pattern, lane, enabled)`. `init_db(conn)` migrates old DBs in place.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_migration.py
import sqlite3
import db


def _cols(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def test_fresh_db_has_lane_and_rules(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    db.init_db(conn)
    assert {"lane", "is_bulk"} <= _cols(conn, "messages")
    assert {"id", "position", "field", "pattern", "lane", "enabled"} <= _cols(conn, "rules")


def test_existing_db_is_migrated(tmp_path):
    # build a phase-1 style DB lacking the new columns
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, subject TEXT)")
    raw.commit()
    raw.close()
    conn = db.connect(path)
    db.init_db(conn)
    assert {"lane", "is_bulk"} <= _cols(conn, "messages")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_db_migration.py -q`
Expected: FAIL (`lane` not in columns).

- [ ] **Step 3: Implement**

In `db.py`, append to `SCHEMA` (before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    position INTEGER NOT NULL DEFAULT 0,
    field TEXT NOT NULL,
    pattern TEXT NOT NULL,
    lane TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
```

Replace `init_db` with:

```python
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
```

Note: `CREATE TABLE IF NOT EXISTS messages` in SCHEMA does not add columns to an existing table — `_migrate` covers old DBs; fresh DBs get the columns from `_migrate` too (keep the base CREATE TABLE unchanged so the FTS triggers' column lists stay valid).

- [ ] **Step 4: Run tests**

Run: `venv/bin/python -m pytest tests/test_db_migration.py -q` → PASS, then full suite `venv/bin/python -m pytest -q` → all green.

- [ ] **Step 5: Commit** — `git add db.py tests/test_db_migration.py && git commit -m "feat: schema for lanes + rules (with in-place migration)"`

---

### Task 2: mailparse — detect bulk mail headers

**Files:**
- Modify: `mailparse.py`
- Test: `tests/test_mailparse_bulk.py` (create)

**Interfaces:**
- Produces: `parse_rfc822(raw)["is_bulk"]` — `1` when `List-Unsubscribe` or `List-Id` header present, else `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mailparse_bulk.py
from mailparse import parse_rfc822

BULK = (b"From: Offers <offers@shop.com>\r\nTo: me@x.com\r\n"
        b"Subject: SALE\r\nList-Unsubscribe: <mailto:u@shop.com>\r\n"
        b"\r\nbuy things")
PLAIN = (b"From: Liz <liz@example.org>\r\nTo: me@x.com\r\n"
         b"Subject: hi\r\n\r\nhello")


def test_list_unsubscribe_marks_bulk():
    assert parse_rfc822(BULK)["is_bulk"] == 1


def test_plain_mail_not_bulk():
    assert parse_rfc822(PLAIN)["is_bulk"] == 0
```

- [ ] **Step 2: Run to verify FAIL** — `venv/bin/python -m pytest tests/test_mailparse_bulk.py -q` → KeyError `is_bulk`.

- [ ] **Step 3: Implement** — in `parse_rfc822`'s return dict add:

```python
"is_bulk": 1 if (msg.get("List-Unsubscribe") or msg.get("List-Id")) else 0,
```

- [ ] **Step 4: Run tests** — file PASS, full suite green (note: `store.upsert_message` doesn't read `is_bulk` yet — Task 4 wires it).

- [ ] **Step 5: Commit** — `git commit -am "feat: parse bulk-mail list headers into is_bulk"`

---

### Task 3: rules.py — pure classifier

**Files:**
- Create: `rules.py`
- Test: `tests/test_rules.py`

**Interfaces:**
- Consumes: message dict with keys `from_email`, `subject`, `is_bulk` (missing keys tolerated).
- Produces: `LANES = ("people", "newsletters", "receipts", "notifications")`; `classify(msg, user_rules=()) -> str`. A user rule is a dict `{"field": "from_email"|"from_domain"|"subject", "pattern": str, "lane": str, "enabled": 1}`; first enabled match wins; patterns are case-insensitive substrings.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rules.py
import rules


def m(from_email="a@b.com", subject="hi", is_bulk=0):
    return {"from_email": from_email, "subject": subject, "is_bulk": is_bulk}


def test_receipt_subject():
    assert rules.classify(m(subject="Your receipt #4821 from Stripe")) == "receipts"


def test_order_confirmation():
    assert rules.classify(m(subject="Order Confirmation - eBay", is_bulk=1)) == "receipts"


def test_social_domain_is_notification():
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1)) == "notifications"


def test_noreply_localpart_is_notification():
    assert rules.classify(m(from_email="no-reply@somesite.io")) == "notifications"


def test_bulk_header_is_newsletter():
    assert rules.classify(m(from_email="olly@storylearning.com", is_bulk=1)) == "newsletters"


def test_marketing_localpart_is_newsletter():
    assert rules.classify(m(from_email="offers@wish.com")) == "newsletters"


def test_plain_human_is_people():
    assert rules.classify(m(from_email="liz.beard@villeplatterotary.org")) == "people"


def test_user_rule_wins_over_heuristics():
    r = [{"field": "from_domain", "pattern": "twitter.com",
          "lane": "people", "enabled": 1}]
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1), r) == "people"


def test_disabled_rule_ignored():
    r = [{"field": "from_domain", "pattern": "twitter.com",
          "lane": "people", "enabled": 0}]
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1), r) == "notifications"


def test_subject_rule_substring_case_insensitive():
    r = [{"field": "subject", "pattern": "OMNICHROME",
          "lane": "people", "enabled": 1}]
    assert rules.classify(m(subject="omnichrome invoice", is_bulk=1), r) == "people"
```

- [ ] **Step 2: Run to verify FAIL** — `venv/bin/python -m pytest tests/test_rules.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement `rules.py`**

```python
"""Deterministic lane classification: user rules first, then heuristics.

Heuristic lists tuned against the 2026-08-18 survey of the operator's
51k-message inbox (top senders/domains).
"""

import re

LANES = ("people", "newsletters", "receipts", "notifications")

_RECEIPT_SUBJECT = re.compile(
    r"\b(receipt|invoice|order (confirm\w*|#|no\.?)|payment|statement"
    r"|shipped|shipping confirmation|your order|purchase)\b", re.IGNORECASE)
_RECEIPT_LOCAL = {"billing", "receipts", "invoice", "invoicing", "payments"}

_NOTIF_DOMAINS = {
    "twitter.com", "x.com", "facebookmail.com", "redditmail.com",
    "twitch.tv", "youtube.com", "accounts.google.com", "linkedin.com",
    "quora.com", "gamejolt.com", "discord.com", "github.com",
    "announcements.soundcloud.com",
}
_NOTIF_LOCAL = re.compile(
    r"^(no-?reply|do-?not-?reply|notifications?|alerts?|mailer-daemon"
    r"|friendupdates|notification\+.*)$", re.IGNORECASE)

_NEWS_LOCAL = {"newsletter", "newsletters", "news", "offers", "marketing",
               "deals", "digest", "promotions", "promo", "hello", "info",
               "store", "sales", "support"}


def _split(addr):
    addr = (addr or "").lower()
    local, _, domain = addr.partition("@")
    return local, domain


def _field_value(msg, field):
    if field == "from_domain":
        return _split(msg.get("from_email"))[1]
    return (msg.get(field) or "").lower()


def classify(msg, user_rules=()):
    for r in user_rules:
        if not r.get("enabled", 1):
            continue
        if (r.get("pattern") or "").lower() in _field_value(msg, r.get("field", "")):
            if r.get("pattern") and r.get("lane") in LANES:
                return r["lane"]
    local, domain = _split(msg.get("from_email"))
    subject = msg.get("subject") or ""
    if _RECEIPT_SUBJECT.search(subject) or local in _RECEIPT_LOCAL:
        return "receipts"
    if domain in _NOTIF_DOMAINS or _NOTIF_LOCAL.match(local):
        return "notifications"
    if msg.get("is_bulk") or local in _NEWS_LOCAL:
        return "newsletters"
    return "people"
```

- [ ] **Step 4: Run tests** — file PASS, full suite green.

- [ ] **Step 5: Commit** — `git add rules.py tests/test_rules.py && git commit -m "feat: lane classifier (user rules + survey-tuned heuristics)"`

---

### Task 4: store — persist lanes, rules CRUD, lane queries, reclassify

**Files:**
- Modify: `store.py` (also `LIST_COLUMNS` gains `m.lane`)
- Test: `tests/test_store_lanes.py` (create)

**Interfaces:**
- Consumes: `rules.classify` (Task 3).
- Produces:
  - `upsert_message` stores `parsed.get("is_bulk", 0)` and `parsed.get("lane", "")`.
  - `list_messages(conn, account_id=None, lane=None, limit, offset)`.
  - `lane_counts(conn) -> {lane: {"total": n, "unread": n}}`.
  - `list_rules(conn) -> [dict]` (ordered by position, id); `add_rule(conn, field, pattern, lane) -> id` (position = max+1; raises `ValueError` on bad field/lane/empty pattern); `delete_rule(conn, rule_id)`.
  - `reclassify_all(conn)` — recomputes `lane` for every message using current rules; returns count changed.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store_lanes.py
import db
import store
import pytest


def _conn(tmp_path):
    c = db.connect(tmp_path / "m.db")
    db.init_db(c)
    return c


def _msg(**kw):
    base = {"message_id": "", "thread_key": "", "from_name": "",
            "from_email": "offers@wish.com", "to_json": "[]",
            "date_utc": "2026-08-18T00:00:00Z", "subject": "sale",
            "body_text": "b", "body_html": "", "snippet": "b",
            "is_bulk": 1, "lane": "newsletters"}
    base.update(kw)
    return base


def test_upsert_stores_lane_and_bulk(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    mid = store.upsert_message(c, a, "INBOX", 1, _msg())
    row = store.get_message(c, mid)
    assert row["lane"] == "newsletters"


def test_list_messages_lane_filter(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())
    store.upsert_message(c, a, "INBOX", 2,
                         _msg(from_email="liz@example.org", lane="people"))
    out = store.list_messages(c, lane="people")
    assert [m["from_email"] for m in out] == ["liz@example.org"]


def test_lane_counts(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())
    counts = store.lane_counts(c)
    assert counts["newsletters"]["total"] == 1
    assert counts["newsletters"]["unread"] == 1


def test_rules_crud_and_validation(tmp_path):
    c = _conn(tmp_path)
    rid = store.add_rule(c, "from_domain", "twitter.com", "people")
    assert [r["id"] for r in store.list_rules(c)] == [rid]
    with pytest.raises(ValueError):
        store.add_rule(c, "bogus_field", "x", "people")
    with pytest.raises(ValueError):
        store.add_rule(c, "subject", "x", "bogus_lane")
    with pytest.raises(ValueError):
        store.add_rule(c, "subject", "  ", "people")
    store.delete_rule(c, rid)
    assert store.list_rules(c) == []


def test_reclassify_all_applies_new_rule(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())  # newsletters
    store.add_rule(c, "from_domain", "wish.com", "people")
    changed = store.reclassify_all(c)
    assert changed == 1
    assert store.list_messages(c, lane="people")[0]["from_email"] == "offers@wish.com"
```

- [ ] **Step 2: Run to verify FAIL** — `venv/bin/python -m pytest tests/test_store_lanes.py -q`.

- [ ] **Step 3: Implement in `store.py`**

Add `import rules as rules_mod` at top. Change `LIST_COLUMNS` to end with `" m.is_read, m.lane"`. In `upsert_message`, extend the INSERT column list with `is_bulk, lane` and values `parsed.get("is_bulk", 0), parsed.get("lane", "")`. Replace `list_messages` and append new functions:

```python
def list_messages(conn, account_id=None, lane=None, limit=100, offset=0):
    sql = (f"SELECT {LIST_COLUMNS} FROM messages m"
           " JOIN accounts a ON a.id = m.account_id")
    where, args = [], []
    if account_id is not None:
        where.append("m.account_id = ?")
        args.append(account_id)
    if lane:
        where.append("m.lane = ?")
        args.append(lane)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY m.date_utc DESC, m.id DESC LIMIT ? OFFSET ?"
    args += [limit, offset]
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def lane_counts(conn):
    rows = conn.execute(
        "SELECT lane, COUNT(*) AS total,"
        " SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) AS unread"
        " FROM messages GROUP BY lane").fetchall()
    out = {ln: {"total": 0, "unread": 0} for ln in rules_mod.LANES}
    for r in rows:
        key = r["lane"] if r["lane"] in out else "people"
        out[key]["total"] += r["total"]
        out[key]["unread"] += r["unread"] or 0
    return out


RULE_FIELDS = ("from_email", "from_domain", "subject")


def list_rules(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, position, field, pattern, lane, enabled FROM rules"
        " ORDER BY position, id").fetchall()]


def add_rule(conn, field, pattern, lane):
    if field not in RULE_FIELDS:
        raise ValueError(f"field must be one of {RULE_FIELDS}")
    if lane not in rules_mod.LANES:
        raise ValueError(f"lane must be one of {rules_mod.LANES}")
    pattern = (pattern or "").strip()
    if not pattern:
        raise ValueError("pattern must be non-empty")
    pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM rules"
                       ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO rules (position, field, pattern, lane) VALUES (?,?,?,?)",
        (pos, field, pattern, lane))
    conn.commit()
    return cur.lastrowid


def delete_rule(conn, rule_id):
    conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))
    conn.commit()


def reclassify_all(conn):
    user_rules = list_rules(conn)
    changed = 0
    rows = conn.execute(
        "SELECT id, from_email, subject, is_bulk, lane FROM messages").fetchall()
    for r in rows:
        new = rules_mod.classify(dict(r), user_rules)
        if new != r["lane"]:
            conn.execute("UPDATE messages SET lane=? WHERE id=?", (new, r["id"]))
            changed += 1
    conn.commit()
    return changed
```

- [ ] **Step 4: Run tests** — file PASS; full suite green (existing `store` tests unaffected: new params default to old behavior).

- [ ] **Step 5: Commit** — `git commit -am "feat: lane persistence, rules CRUD, reclassify in store"`

---

### Task 5: sync — classify at ingest

**Files:**
- Modify: `sync.py` (inside `sync_account`, around the fetch loop at lines 49-62)
- Test: `tests/test_sync_lanes.py` (create)

**Interfaces:**
- Consumes: `store.list_rules`, `rules.classify`.
- Produces: every message stored by `sync_account` carries a computed `lane` (and `is_bulk` from the parser). User rules are loaded once per `sync_account` call.

- [ ] **Step 1: Write the failing test**

Follow the existing pattern in `tests/` that uses `fakes.FakeIMAPClient` (read `tests/fakes.py` first and mirror how current sync tests construct it):

```python
# tests/test_sync_lanes.py
import db
import store
import sync
from tests.fakes import FakeIMAPClient
from accounts import Account  # match the real constructor used by other tests

BULK = (b"From: Offers <offers@wish.com>\r\nTo: me@x.com\r\n"
        b"Subject: SALE\r\nList-Unsubscribe: <mailto:u@wish.com>\r\n"
        b"\r\nbuy")


def test_synced_message_gets_lane(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    db.init_db(conn)
    client = FakeIMAPClient({"INBOX": {1: BULK}})
    acct = Account(email="x@y.com", provider="gmail", password="p")
    sync.sync_account(conn, acct, client=client)
    msgs = store.list_messages(conn, lane="newsletters")
    assert len(msgs) == 1


def test_user_rule_applies_during_sync(tmp_path):
    conn = db.connect(tmp_path / "m.db")
    db.init_db(conn)
    store.add_rule(conn, "from_domain", "wish.com", "people")
    client = FakeIMAPClient({"INBOX": {1: BULK}})
    acct = Account(email="x@y.com", provider="gmail", password="p")
    sync.sync_account(conn, acct, client=client)
    assert len(store.list_messages(conn, lane="people")) == 1
```

(If `Account`'s constructor differs, mirror the real signature from `accounts.py` / existing sync tests — do not change `accounts.py`.)

- [ ] **Step 2: Run to verify FAIL** — lane column empty, filter returns nothing.

- [ ] **Step 3: Implement** — in `sync.py` add `import rules as rules_mod` at top. In `sync_account`, after `acct_id = ...` add `user_rules = store.list_rules(conn)`. In the fetch loop replace the `store.upsert_message(...)` call with:

```python
parsed = parse_rfc822(raw)
parsed["lane"] = rules_mod.classify(parsed, user_rules)
store.upsert_message(conn, acct_id, folder, uid, parsed)
```

- [ ] **Step 4: Run tests** — file PASS, full suite green.

- [ ] **Step 5: Commit** — `git commit -am "feat: classify messages into lanes at sync ingest"`

---

### Task 6: API — lane filter, lane counts, rules endpoints

**Files:**
- Modify: `app.py`
- Test: `tests/test_lanes_api.py` (create)

**Interfaces:**
- Produces:
  - `GET /api/messages?lane=<lane>` filters (combines with existing `account`/`q`; for `q` searches, filter the search results in Python by `m["lane"]`).
  - `GET /api/lanes` → `{"lanes": {<lane>: {"total": n, "unread": n}}}`.
  - `GET /api/rules` → `{"rules": [...]}`; `POST /api/rules` body `{"field","pattern","lane"}` → `{"id": n}` (400 + `{"error": msg}` on ValueError) — then runs `reclassify_all`; `DELETE /api/rules/<int:rid>` → `{"ok": true}` — then runs `reclassify_all`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lanes_api.py
import db
import store
from app import create_app


def _client(tmp_path):
    app = create_app(db_path=tmp_path / "m.db")
    return app.test_client()


def _seed(tmp_path):
    c = db.connect(tmp_path / "m.db")
    db.init_db(c)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, {
        "message_id": "", "thread_key": "", "from_name": "",
        "from_email": "offers@wish.com", "to_json": "[]",
        "date_utc": "2026-08-18T00:00:00Z", "subject": "sale",
        "body_text": "b", "body_html": "", "snippet": "b",
        "is_bulk": 1, "lane": "newsletters"})
    c.close()


def test_lane_filter(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    assert len(cl.get("/api/messages?lane=newsletters").json["messages"]) == 1
    assert cl.get("/api/messages?lane=people").json["messages"] == []


def test_lane_counts_endpoint(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    lanes = cl.get("/api/lanes").json["lanes"]
    assert lanes["newsletters"]["total"] == 1


def test_rules_crud_reclassifies(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    r = cl.post("/api/rules", json={"field": "from_domain",
                                    "pattern": "wish.com", "lane": "people"})
    assert r.status_code == 200
    rid = r.json["id"]
    assert len(cl.get("/api/messages?lane=people").json["messages"]) == 1
    assert cl.post("/api/rules", json={"field": "nope", "pattern": "x",
                                       "lane": "people"}).status_code == 400
    assert cl.delete(f"/api/rules/{rid}").json["ok"] is True
    assert cl.get("/api/messages?lane=people").json["messages"] == []
```

- [ ] **Step 2: Run to verify FAIL**.

- [ ] **Step 3: Implement in `app.py`** — in `list_messages`, read `lane = request.args.get("lane") or None`, pass to `store.list_messages(...)`; in the `q` branch add `if lane: msgs = [m for m in msgs if m.get("lane") == lane]`. Add routes:

```python
    @app.get("/api/lanes")
    def lanes():
        return jsonify({"lanes": store.lane_counts(conn())})

    @app.get("/api/rules")
    def get_rules():
        return jsonify({"rules": store.list_rules(conn())})

    @app.post("/api/rules")
    def post_rule():
        body = request.get_json(silent=True) or {}
        try:
            rid = store.add_rule(conn(), body.get("field"),
                                 body.get("pattern"), body.get("lane"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        store.reclassify_all(conn())
        return jsonify({"id": rid})

    @app.delete("/api/rules/<int:rid>")
    def del_rule(rid):
        store.delete_rule(conn(), rid)
        store.reclassify_all(conn())
        return jsonify({"ok": True})
```

- [ ] **Step 4: Run tests** — file PASS, full suite green.

- [ ] **Step 5: Commit** — `git commit -am "feat: lanes + rules API"`

---

### Task 7: UI — lane chips + rules panel

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `/api/lanes`, `/api/messages?lane=`, `/api/rules` (Task 6 shapes).

- [ ] **Step 1: Read `static/index.html` fully** to learn its existing chip/filter/render structure (phase 1 built account chips + search; mirror those patterns and styles exactly — no restyling).

- [ ] **Step 2: Implement**
  - A lane chip row next to the account chips: `All`, `People`, `Newsletters`, `Receipts`, `Notifications`, each showing `unread` from `/api/lanes` (e.g. `People (3)`); clicking sets a `state.lane` filter and re-fetches `/api/messages` with `&lane=`; `All` clears it. Refresh counts whenever messages are re-fetched.
  - A small `Rules` toggle button that shows/hides a panel: existing rules listed as `field contains "pattern" → lane` with a delete `×` per rule, plus an add-row (select field: From address / From domain / Subject; text input; select lane; Add button → `POST /api/rules`, then refresh rules, counts and list). Show `error` text from a 400 response inline.
  - Keep it in the file's existing vanilla-JS style (no frameworks, no new fonts/colors).

- [ ] **Step 3: Manual verification** — `MAILHUB_NO_SYNC=1 venv/bin/python app.py` and check in a browser (or the repo's `verify` approach): chips render with counts, clicking filters, adding a rule `from_domain` `wish.com` → `people` moves messages, deleting it moves them back.

- [ ] **Step 4: Run full suite** — `venv/bin/python -m pytest -q` green.

- [ ] **Step 5: Commit** — `git commit -am "feat: lane chips + rules panel in UI"`

---

### Task 8: Live rollout — reclassify real data, e2e check, merge

**Files:**
- None (operational) — uses `store.reclassify_all`.

- [ ] **Step 1: Reclassify existing local messages** (they were ingested pre-lanes with `lane=''`; `is_bulk` is also 0 for them, so bulk-header detection only applies to newly synced mail — acceptable: the heuristics still use sender/subject, and the DB only holds recent messages):

```bash
venv/bin/python -c "
import db, store
from pathlib import Path
c = db.connect(Path.home()/'.mailhub'/'mailhub.db'); db.init_db(c)
print('reclassified:', store.reclassify_all(c))"
```

- [ ] **Step 2: Restart the app** (kill any running `app.py`, relaunch via `./launch.sh` or the desktop icon) and confirm `/api/lanes` returns sensible counts against the real mailbox.

- [ ] **Step 3: e2e sanity in the UI** — lanes populated; personal senders land in People; a known marketing sender in Newsletters.

- [ ] **Step 4: Merge** — use superpowers:finishing-a-development-branch (merge `phase-3-lanes` → `master`).

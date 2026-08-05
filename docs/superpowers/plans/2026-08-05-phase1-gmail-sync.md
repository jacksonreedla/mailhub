# Mailhub Phase 1 Implementation Plan — Skeleton + Gmail IMAP Sync + Unified List UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask app at `localhost:8770` that syncs one or more Gmail accounts over IMAP (app passwords) into SQLite+FTS5 and shows them as one searchable unified list.

**Architecture:** Flat-module Flask app mirroring `~/docbot` (single `app.py`, sibling modules, `static/` SPA, `tests/`, local venv). A background thread syncs each account incrementally by IMAP UID into a normalized `messages` table with an FTS5 mirror. Read-only against providers; all state is local.

**Tech Stack:** Python 3.12, Flask, imapclient, SQLite (stdlib `sqlite3`, FTS5), bleach (HTML sanitizing), pytest.

## Global Constraints

- Repo: `~/mailhub` (own git). Port **8770**, bound to `127.0.0.1` only.
- Read-only against providers: never store/set flags on the server, never delete, no SMTP.
- Secrets (app passwords) live only in `~/.mailhub/credentials.json` chmod 600 — never in the repo, never printed, never logged.
- DB at `~/.mailhub/mailhub.db` (override with env `MAILHUB_DB` for tests).
- No UI aesthetic work in this phase (plain functional HTML) — the Telegraph Exchange design track skins it later.
- TDD: every task = failing test → minimal code → pass → commit.

## File Structure

- `db.py` — schema + connection helper (`connect(path)`, `init_db(conn)`); FTS5 virtual table + sync triggers.
- `store.py` — message persistence/query API (`upsert_message`, `list_messages`, `search_messages`, `get_message`, sync-state get/set).
- `mailparse.py` — RFC822 → normalized dict (`parse_rfc822(raw_bytes) -> dict`), HTML sanitizing.
- `accounts.py` — account registry from `~/.mailhub/credentials.json` (`load_accounts() -> list[Account]`).
- `sync.py` — IMAP incremental sync engine (`sync_account(conn, account, client=None)`), UID tracking, `SyncDaemon` thread.
- `app.py` — Flask app + JSON API + static serving.
- `static/index.html` — minimal SPA: unified list, account chips, search box, message reader.
- `tests/` — `test_db.py`, `test_store.py`, `test_mailparse.py`, `test_sync.py`, `test_api.py`; `tests/fixtures/` sample RFC822 files; fake IMAP client in `tests/fakes.py`.

---

### Task 1: Repo scaffolding + DB schema

**Files:**
- Create: `db.py`, `requirements.txt`, `.gitignore`, `README.md`, `tests/test_db.py`

**Interfaces:**
- Produces: `db.connect(path) -> sqlite3.Connection` (row_factory=Row, WAL, foreign keys on); `db.init_db(conn)` idempotent; tables `accounts(id, email, provider, display_name)`, `messages(id INTEGER PK, account_id, uid INTEGER, folder TEXT, message_id TEXT, thread_key TEXT, from_name, from_email, to_json, date_utc TEXT, subject, body_text, body_html, snippet, is_read INTEGER DEFAULT 0, created_at)`, unique `(account_id, folder, uid)`; `sync_state(account_id, folder, uidvalidity INTEGER, last_uid INTEGER, PRIMARY KEY(account_id, folder))`; FTS5 table `messages_fts(subject, body_text, from_email, content='messages', content_rowid='id')` with INSERT/UPDATE/DELETE triggers.

- [ ] Write `tests/test_db.py`: `init_db` creates tables (query `sqlite_master`), is idempotent (call twice), FTS row appears after raw INSERT into `messages` and disappears after DELETE.
- [ ] Run `venv/bin/python -m pytest tests/test_db.py -v` → FAIL (no db module).
- [ ] Implement `db.py`; create venv, `requirements.txt` (`flask`, `imapclient`, `bleach`, `pytest`), `.gitignore` (`venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`), short `README.md`.
- [ ] Tests pass. Commit `feat: repo skeleton + sqlite schema with FTS5`.

### Task 2: Message parsing (`mailparse.py`)

**Files:**
- Create: `mailparse.py`, `tests/test_mailparse.py`, `tests/fixtures/*.eml` (write 4 fixtures inline in the test file or as files: plain-text; multipart text+html; html-only with `<script>`; UTF-8/encoded-words headers with attachment)

**Interfaces:**
- Produces: `parse_rfc822(raw: bytes) -> dict` with keys `message_id, thread_key, from_name, from_email, to_json, date_utc (ISO 8601 UTC), subject, body_text, body_html (sanitized), snippet (first 160 chars of text)`. `thread_key` = normalized subject (strip `Re:/Fwd:` prefixes, casefold) — good enough for Phase 1. Uses stdlib `email` with `policy.default`; sanitize HTML with `bleach.clean(..., strip=True)` allowing basic formatting tags + `a[href]`, drop `script/style/img` (imgs stripped in Phase 1 = no tracking pixels).

- [ ] Write tests: correct fields per fixture; `<script>` never survives; encoded-word subject decodes; missing Date header → `date_utc` falls back to empty string, not crash.
- [ ] Run → FAIL. Implement `mailparse.py`. Pass. Commit `feat: rfc822 parsing + html sanitization`.

### Task 3: Store layer (`store.py`)

**Files:**
- Create: `store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `db.connect/init_db`, parsed dicts from `mailparse`.
- Produces: `upsert_account(conn, email, provider, display_name) -> account_id`; `upsert_message(conn, account_id, folder, uid, parsed: dict) -> id` (INSERT OR IGNORE on `(account_id, folder, uid)`); `list_messages(conn, account_id=None, limit=100, offset=0) -> list[dict]` newest-first with account email joined; `search_messages(conn, query, limit=100) -> list[dict]` via FTS5 MATCH (escape user input by wrapping each term in double quotes); `get_message(conn, id) -> dict|None` (full bodies); `mark_read(conn, id, read=True)` local-only; `get_sync_state(conn, account_id, folder) -> (uidvalidity, last_uid)|None`, `set_sync_state(conn, account_id, folder, uidvalidity, last_uid)`.

- [ ] Write tests: upsert dedupes on same UID; list merges two accounts newest-first; search finds subject and body terms, quoted-phrase input with `"` doesn't raise; sync state round-trips and overwrites.
- [ ] Run → FAIL. Implement. Pass. Commit `feat: message store + fts search + sync state`.

### Task 4: Accounts registry (`accounts.py`)

**Files:**
- Create: `accounts.py`, `tests/test_accounts.py`

**Interfaces:**
- Produces: `Account` dataclass `(email, provider, imap_host, username, password, display_name)`; `load_accounts(path=None) -> list[Account]` reading JSON `{"accounts": [{"email":..., "provider":"gmail", "password":...}]}` from `path` or `~/.mailhub/credentials.json`; gmail provider defaults `imap_host="imap.gmail.com"`, `username=email`. Missing file → `[]`. Also `ensure_config_dir()` creating `~/.mailhub` chmod 700, and a `credentials.json.example` written to repo (fake values only).

- [ ] Write tests (use tmp_path): loads gmail account with host default; missing file → empty list; malformed JSON → raises `ValueError` with filename (no password in message).
- [ ] Run → FAIL. Implement. Pass. Commit `feat: account registry from local credentials file`.

### Task 5: IMAP sync engine (`sync.py`)

**Files:**
- Create: `sync.py`, `tests/fakes.py`, `tests/test_sync.py`

**Interfaces:**
- Consumes: `store.*`, `mailparse.parse_rfc822`, `accounts.Account`.
- Produces: `sync_account(conn, account, client=None, folder="INBOX", batch=50) -> int` (returns # new messages). Logic: build client via `imapclient.IMAPClient(host, ssl=True)` + `login` unless injected; `select_folder(folder, readonly=True)`; compare `UIDVALIDITY` to stored — if changed, wipe that account+folder's messages and resync; first sync fetches only the most recent 200 UIDs (`search('ALL')[-200:]`); incremental = `search(['UID', f'{last_uid+1}:*'])` filtered `> last_uid`; fetch `RFC822` in batches of `batch`; parse → upsert; update sync state after each batch (crash-safe). `SyncDaemon(db_path, interval=180)` thread: loops accounts, opens its own connection, calls `sync_account`, logs per-account errors to stderr and continues (one bad account never kills the loop), `daemon=True`, `stop()` via `threading.Event`.
- Fake: `tests/fakes.py` `FakeIMAPClient` implementing `select_folder/search/fetch/logout` over an in-memory dict `{uid: raw_bytes}` with settable `uidvalidity`.

- [ ] Write tests: first sync ingests all fake messages and sets last_uid; second sync with no new mail ingests 0; new message appears after adding uid; UIDVALIDITY change wipes and resyncs; fetch exception mid-batch leaves earlier batch persisted (sync state advanced per batch).
- [ ] Run → FAIL. Implement. Pass. Commit `feat: incremental imap sync engine with uid tracking`.

### Task 6: Flask API + SPA (`app.py`, `static/index.html`)

**Files:**
- Create: `app.py`, `static/index.html`, `launch.sh`, `tests/test_api.py`

**Interfaces:**
- Consumes: everything above.
- Produces: routes `GET /` (static index), `GET /api/messages?account=&q=&limit=&offset=` (unified list; `q` → `search_messages`), `GET /api/messages/<int:id>` (full message; body_html already sanitized), `POST /api/messages/<int:id>/read` `{read: bool}`, `GET /api/accounts` (accounts + message counts), `POST /api/sync` (trigger immediate sync pass in background), `GET /api/status` (per-account last sync time/error, daemon alive). App factory `create_app(db_path=None)` so tests inject tmp DB and skip the daemon (`MAILHUB_NO_SYNC=1`). `__main__`: init db, load accounts, start `SyncDaemon`, `app.run(host="127.0.0.1", port=8770)`. `launch.sh` mirrors docbot's.
- SPA (plain functional, no styling beyond readable defaults): account filter chips, search input (debounced, hits `/api/messages?q=`), unified list rows (account badge, from, subject, snippet, date), click → fetch full message, render `body_html` inside `<iframe sandbox srcdoc>` (fallback `body_text` in `<pre>`), mark-read on open, "Open in Gmail" link `https://mail.google.com/mail/u/<account-email>/#search/rfc822msgid:<url-encoded message_id>`.

- [ ] Write API tests with Flask test client + seeded tmp DB: list merges accounts; `q=` filters; single fetch returns bodies; read toggles; unknown id → 404; `/api/accounts` counts correct.
- [ ] Run → FAIL. Implement `app.py`. Pass.
- [ ] Write `static/index.html`; manual check `venv/bin/python app.py` serves it.
- [ ] Commit `feat: flask api + unified list spa`.

### Task 7: End-to-end with a real Gmail account (operator-assisted)

**Files:**
- Modify: none (config only, outside repo)

- [ ] Guide the operator: enable 2FA on one Gmail account → create app password → fill `~/.mailhub/credentials.json` (agent writes the file structure with placeholder, operator pastes the password, or operator runs a provided one-liner; the password is never echoed).
- [ ] Run `venv/bin/python app.py`; verify: real messages appear within one sync interval, search returns a known subject, message opens with sanitized HTML, "Open in Gmail" lands on the right thread, restart resumes without duplicates (`SELECT COUNT(*)` stable across restart+sync).
- [ ] Full suite `venv/bin/python -m pytest -q` green. Commit any fixes. Tag `phase-1`.

## Self-review notes

- Spec coverage: skeleton ✔ (T1), Gmail IMAP app-password sync ✔ (T4/T5), SQLite+FTS5 ✔ (T1/T3), unified list + search UI ✔ (T6), read-only + local-state ✔ (constraints, T3 mark_read local), restart resilience ✔ (T5 state-per-batch + T7 check). Microsoft/rules/AI are later phases by design.
- Deep-link uses `rfc822msgid:` search — works with the multi-login `u/<email>` selector.

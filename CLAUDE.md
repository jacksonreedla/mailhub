# Mailhub — Engineering Context

*Onboarding doc for any AI/engineer session in this repo. Last updated
2026-08-05 (phase 1 merged). Keep this current when architecture or status
changes.*

**What this is:** the operator's **personal unified email triage dashboard** —
all their email accounts in one local place, organized by rules + local AI.
Explicitly **NOT part of the OmniChrome suite**: no Omni branding, no
OmniChrome design system, no shared infra, nothing deployed to the Hetzner
box. OmniChrome-related mail accounts will simply be among the accounts
linked here. Working name "Mailhub" (user may rename).

## Core decisions (locked in during design — don't re-litigate silently)

- **Local-only web app** on `127.0.0.1:8770` (DocBot pattern, see `~/docbot`).
  Never bind beyond localhost; never deploy to a server.
- **Read/triage only — the app NEVER sends mail and never writes to
  providers.** No SMTP, no send scopes, no server-side flag changes
  (folders open `readonly=True`). Replying = local AI drafts text → user
  copies it → "Open in Gmail/Outlook" deep link to send there.
- **Gmail = IMAP + per-account app passwords** (chosen over OAuth because
  Google's unverified-app testing mode expires refresh tokens every 7 days).
- **Microsoft = Graph API OAuth** (`Mail.Read` + `offline_access` only,
  MSAL device-code flow, free Azure app registration by the operator) —
  basic-auth IMAP is dead for outlook.com. Not built yet (phase 2).
- **Secrets:** `~/.mailhub/credentials.json` (chmod 600) — never in the
  repo, never printed, never logged. Template: `credentials.json.example`.
  DB lives at `~/.mailhub/mailhub.db` (`MAILHUB_DB` env overrides; tests
  use tmp paths).

## Status (2026-08-05)

- **Phase 1 DONE + merged to master:** skeleton, Gmail IMAP incremental
  sync, SQLite+FTS5 store, unified list SPA with search/reader/deep-links.
  35 pytest tests green.
- **Phase 1 live e2e PENDING (operator):** needs one real Gmail app
  password in `~/.mailhub/credentials.json`, then verify live sync,
  search, reader, deep link, restart-without-duplicates. Tag `phase-1`
  after it passes.
- Remaining phases per plan: 2 Microsoft Graph → 3 rules + lanes →
  4 AI layer (Ollama) → 5 polish (snooze, keyboard nav, systemd user unit).

## Layout

Flat modules, no framework magic:

- `db.py` — schema (accounts/messages/sync_state + `messages_fts` FTS5 with
  insert/update/delete triggers), `connect()` (WAL, Row factory), `init_db()`.
- `mailparse.py` — `parse_rfc822(bytes) -> dict`; bleach-sanitized HTML
  (script/style bodies regex-stripped BEFORE bleach — bleach keeps inner
  text otherwise), imgs stripped in phase 1 (= no tracking pixels),
  `thread_key` = Re/Fwd-stripped casefolded subject.
- `store.py` — upserts (dedupe on `(account_id, folder, uid)`), list/search
  (`_fts_query` wraps every term in quotes so user input can't hit FTS5
  operators), `get_message`, local-only `mark_read`, sync-state get/set.
- `accounts.py` — `load_accounts()` from credentials.json; gmail defaults
  `imap.gmail.com`.
- `sync.py` — `sync_account()` (UID-incremental, per-batch state commits =
  crash-safe resume; UIDVALIDITY change wipes+resyncs that folder; first
  sync capped to most recent 200 via `initial_limit`) + `SyncDaemon`
  thread (per-account try/except, `trigger()` for immediate pass).
- `app.py` — `create_app(db_path, daemon)` factory; routes:
  `GET /api/messages[?q=&account=&limit=&offset=]`, `GET/POST
  /api/messages/<id>[/read]`, `GET /api/accounts`, `POST /api/sync`,
  `GET /api/status`. `main()` starts daemon only if accounts exist and
  `MAILHUB_NO_SYNC` unset.
- `static/index.html` — deliberately plain SPA (chips/search/list/reader,
  sandboxed-iframe HTML, mark-read on open). Do NOT invest style here yet.
- `tests/` — 35 tests incl. `fakes.FakeIMAPClient`. Run:
  `venv/bin/python -m pytest -q`. TDD for all changes.

Run the app: `./launch.sh` (or `venv/bin/python app.py`) → localhost:8770.

## Design track (separate from app phases)

Aesthetic = **"Telegraph Exchange"**: black/white/gray/beige only, 1930s
classical revival × Italian Futurism × esoteric retro-futurist energy.
Achromatic palette (no color accent — radiance instead), Cinzel (engraved
caps) + Jost (Futura revival) + Space Mono, zero border-radius, stepped
Deco frames, messages open as an ivory paper sheet, signature element =
the **Vril dial** (sunburst masthead encoding mail pressure; ray glyphs as
per-row priority). Full spec:
`docs/superpowers/specs/2026-08-05-mailhub-aesthetic-design.md`.

**Process:** the user will drop reference images in a folder (suggested
`~/mailhub-inspo/`; ask if unsure). Step 1 = analyze images, re-derive
exact tokens (current hexes are provisional). Step 2 = static style-tile
HTML page for user approval. Step 3 = skin the app. Do not restyle the
SPA before the style tile is approved.

## Docs

- App spec: `docs/superpowers/specs/2026-08-05-mailhub-app-design.md`
- Aesthetic spec: `docs/superpowers/specs/2026-08-05-mailhub-aesthetic-design.md`
- Phase 1 plan (executed): `docs/superpowers/plans/2026-08-05-phase1-gmail-sync.md`
- Durable memory: `~/.claude/projects/-home-apollo/memory/mailhub-email-dashboard.md`

## Next session quickstart

1. If `~/.mailhub/credentials.json` now exists → run the phase-1 live e2e
   (plan Task 7), tag `phase-1`.
2. If an inspo folder exists → design track step 1 (token derivation +
   style tile).
3. Otherwise → phase 2 (Microsoft Graph) needs a written plan first
   (superpowers writing-plans), then TDD it.

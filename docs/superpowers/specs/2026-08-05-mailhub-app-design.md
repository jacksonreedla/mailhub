# Mailhub — Personal Unified Email Triage Dashboard

> **Naming note:** this is a purely personal tool, NOT part of the OmniChrome
> suite — no Omni-branding, no OmniChrome design system, no shared infra.
> Working name "Mailhub" (`~/mailhub`); the user can rename at any time.
> OmniChrome-related email accounts will simply be among the accounts linked.

## Context

The user has many email accounts (Gmail/Google + Outlook/Hotmail/Microsoft) and wants them all in one place to access and organize. Existing open-source clients (Thunderbird, Cypht, MailFlow) were presented; the user chose a **fully custom-built app**. Requirements gathered:

- **Local web app on this machine** (localhost, same pattern as `~/docbot` — Flask + Ollama), not on the Hetzner box (too small) and not a desktop app.
- **Read-and-triage focus, no sending.** The app fetches, organizes, and summarizes. Replying = AI drafts the reply locally, user copies it and a deep-link opens the message in Gmail/Outlook web UI to paste & send. No send scopes anywhere — much smaller attack/permission surface.
- **Core value = smart organization**: rules & auto-organizing (lanes, tags, priority) + **AI triage & summaries** via the local Ollama stack (private, on-machine).
- NOT OmniChrome work — a standalone personal project (like DocBot/PARRAIN). The user will link their OmniChrome-related email accounts into it, but the app itself shares nothing with the suite.

## Architecture (recommended approach)

New repo `~/mailhub` (own git). Python 3 + Flask + SQLite, mirroring the DocBot layout the user already runs.

```
Providers                Sync engine              Store                UI/API
Gmail (IMAP +        →   background thread    →   SQLite +        →   Flask app
  app passwords)         per account, every       FTS5 index          localhost:8770
MS Graph (OAuth2,        few minutes; fetch       (headers, bodies,   vanilla-JS SPA
  Mail.Read only)        new msgs incremental     lanes, tags,        (unified stream,
                                                  AI annotations)     lanes, search)
                                   ↓
                         Rules engine (user-defined YAML/JSON rules)
                         AI pipeline (Ollama: classify → lane, score
                         priority, 1-line summary, thread summary,
                         draft reply on demand)
```

### Components

1. **`accounts.py` + `sync.py`** — account registry (SQLite table; secrets in a local `.env`/keyring, never printed) and per-account incremental sync.
   - **Gmail:** `imapclient` + app passwords (user enables 2FA per account, generates app password — ~5 min each). UID-based incremental fetch.
   - **Microsoft:** MSAL device-code flow against a free Azure app registration (one-time operator setup, delegated `Mail.Read` + `offline_access` only), Microsoft Graph `/me/messages` delta queries. Personal MS accounts don't suffer Google's 7-day unverified-token expiry.
   - Store raw RFC822/Graph JSON → parsed into a normalized `messages` table (account, thread key, from, to, date, subject, text body, HTML body sanitized with `bleach`).
2. **`rules.py`** — deterministic rules run before AI: match on sender/domain/subject/list-headers → assign lane (People / Newsletters / Receipts / Notifications), tags, archive-locally, mute. Rules editable in the UI, stored in SQLite.
3. **`ai.py`** — Ollama pipeline (reuse DocBot's client pattern at `~/docbot`):
   - per-message: lane classification (only when rules don't decide), importance score 0–3, one-line summary;
   - per-thread: on-demand thread summary;
   - on-demand: draft reply (tone-selectable) with a copy button.
   - All annotations cached in SQLite so each message is processed once.
4. **`app.py` (Flask, localhost:8770)** — JSON API + single-page UI: unified stream grouped by lane, account filter chips, tag filters, FTS5 full-text search, message reader (sanitized HTML in a sandboxed iframe), "Open in Gmail/Outlook" deep links (`https://mail.google.com/mail/u/<email>/#all/<msgid-search>`, `https://outlook.live.com/mail/deeplink/read/<id>`), AI draft panel.
5. **Local-only state** — read/unread, tags, lanes, snooze live in SQLite only; the app never writes to providers (true read-only).

### Why this approach (alternatives considered)

- *Deploy Cypht/MailFlow instead*: faster to email-in-one-place, but neither gives local-LLM triage/lanes — the features the user actually chose. Rejected per user's explicit "fully custom" choice.
- *Gmail API OAuth instead of IMAP*: cleaner API but Google's unverified-app 7-day refresh-token expiry makes it miserable for a personal tool; app passwords are stable. IMAP chosen.
- *Electron/desktop app*: heavier, no benefit over localhost web for this user.

## Build phases

1. **Skeleton + Gmail IMAP sync** — repo, venv, SQLite schema, one Gmail account syncing into a plain unified list UI with search. *Proof of life.*
2. **Microsoft Graph** — Azure app registration walkthrough (operator does the portal clicks; agent provides exact steps), device-code auth, delta sync. All accounts now in one stream.
3. **Rules + lanes UI** — rules engine, default lane heuristics (List-Unsubscribe → Newsletters, etc.), rule editor.
4. **AI layer** — Ollama classification/summaries/priority, thread summary, draft-reply panel with copy + deep link.
5. **Polish** — snooze, tag management, keyboard nav, systemd user unit so it's always running locally.

Each phase is independently usable; TDD per superpowers conventions (pytest; the sync/rules/AI layers are all unit-testable with fixture emails).

## Verification

- `pytest` suite green per phase (parsers, rules, sync state machine with a fake IMAP/Graph server).
- End-to-end: connect one real Gmail (app password) + one real Microsoft account, confirm messages appear in the unified stream, rules file them into lanes, AI annotations populate, search returns known messages, deep links open the right message in the provider web UI.
- Restart resilience: kill/restart the app; sync resumes incrementally without duplicating messages.



## Operator prerequisites (user does these, agent guides)

- Enable 2FA + generate an app password on each Gmail account.
- One-time free Azure "app registration" (agent supplies click-by-click steps) for Microsoft accounts.
- Ollama already installed (DocBot); may pull a better instruct model for classification if dolphin3:8b proves weak.

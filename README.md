# Mailhub

Personal unified email triage dashboard — local-only Flask app that syncs
multiple email accounts (read-only) into SQLite and organizes them with
rules + local AI. See `docs/superpowers/specs/` for the design.

Run: `venv/bin/python app.py` → http://127.0.0.1:8770
Test: `venv/bin/python -m pytest -q`

Credentials live outside the repo in `~/.mailhub/credentials.json` (chmod 600).

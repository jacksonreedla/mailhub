#!/usr/bin/env bash
# Mailhub launcher — run from anywhere.
cd "$(dirname "$0")"
exec venv/bin/python app.py

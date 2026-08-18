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
    return str(msg.get(field) or "").lower()


def classify(msg, user_rules=()):
    for r in user_rules:
        if not r.get("enabled", 1):
            continue
        pattern = (r.get("pattern") or "").lower()
        if pattern and r.get("lane") in LANES \
                and pattern in _field_value(msg, r.get("field", "")):
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

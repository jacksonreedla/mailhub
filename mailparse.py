"""RFC822 → normalized message dict, with HTML sanitization."""

import email
import email.policy
import email.utils
import html
import json
import re

import bleach

ALLOWED_TAGS = [
    "a", "p", "br", "div", "span", "b", "strong", "i", "em", "u", "s",
    "blockquote", "pre", "code", "ul", "ol", "li", "h1", "h2", "h3", "h4",
    "h5", "h6", "table", "thead", "tbody", "tr", "td", "th", "hr",
]
ALLOWED_ATTRS = {"a": ["href", "title"]}

_RE_PREFIX = re.compile(r"^\s*((re|fwd?|aw|sv)\s*:\s*)+", re.IGNORECASE)
_TAG_STRIP = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)


def _thread_key(subject):
    return _RE_PREFIX.sub("", subject or "").strip().casefold()


def _date_utc(msg):
    try:
        dt = email.utils.parsedate_to_datetime(msg.get("Date", ""))
    except (TypeError, ValueError):
        return ""
    if dt is None:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(email.utils.datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _bodies(msg):
    """Return (text, sanitized_html)."""
    text_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    text = text_part.get_content() if text_part else ""
    raw_html = html_part.get_content() if html_part else ""
    clean_html = ""
    if raw_html:
        raw_html = _SCRIPT_STYLE.sub("", raw_html)
        clean_html = bleach.clean(
            raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True
        )
    if not text and clean_html:
        text = html.unescape(_TAG_STRIP.sub(" ", clean_html))
        text = re.sub(r"\s+", " ", text).strip()
    return text, clean_html


def parse_rfc822(raw: bytes) -> dict:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    from_name, from_email = email.utils.parseaddr(msg.get("From", ""))
    to_addrs = [a for _, a in email.utils.getaddresses(msg.get_all("To", [])) if a]
    subject = str(msg.get("Subject", "") or "")
    body_text, body_html = _bodies(msg)
    snippet = re.sub(r"\s+", " ", body_text).strip()[:160]
    return {
        "message_id": str(msg.get("Message-ID", "") or "").strip(),
        "thread_key": _thread_key(subject),
        "from_name": from_name,
        "from_email": from_email,
        "to_json": json.dumps(to_addrs),
        "date_utc": _date_utc(msg),
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "snippet": snippet,
        "is_bulk": 1 if (msg.get("List-Unsubscribe") or msg.get("List-Id")) else 0,
    }

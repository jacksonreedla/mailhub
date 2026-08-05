import json

from mailparse import parse_rfc822

PLAIN = b"""\
From: Sarah K <sarah@example.com>
To: Me <me@example.com>
Subject: Re: lease renewal
Date: Wed, 05 Aug 2026 14:02:00 +0200
Message-ID: <abc123@example.com>
Content-Type: text/plain; charset="utf-8"

Hi, do you want to renew the lease? Let me know by Friday.
"""

MULTIPART = b"""\
From: billing@stripe.com
To: me@example.com
Subject: Receipt #4821
Date: Wed, 05 Aug 2026 13:40:00 +0000
Message-ID: <r4821@stripe.com>
Content-Type: multipart/alternative; boundary="BOUND"

--BOUND
Content-Type: text/plain; charset="utf-8"

Your receipt total is $12.99.
--BOUND
Content-Type: text/html; charset="utf-8"

<html><body><p>Your receipt total is <b>$12.99</b>.</p></body></html>
--BOUND--
"""

EVIL_HTML = b"""\
From: attacker@example.com
To: me@example.com
Subject: click me
Date: Wed, 05 Aug 2026 09:00:00 +0000
Message-ID: <evil@example.com>
Content-Type: text/html; charset="utf-8"

<html><body><script>alert(1)</script><p onclick="x()">hi</p>
<img src="http://track.example.com/p.gif"><a href="https://ok.com">link</a></body></html>
"""

ENCODED = b"""\
From: =?utf-8?B?SsO8cmdlbg==?= <j@example.de>
To: me@example.com
Subject: =?utf-8?B?R3LDvMOfZSBhdXMgTcO8bmNoZW4=?=
Message-ID: <enc@example.de>
Content-Type: text/plain; charset="utf-8"

Servus!
"""


def test_plain_text():
    m = parse_rfc822(PLAIN)
    assert m["from_email"] == "sarah@example.com"
    assert m["from_name"] == "Sarah K"
    assert m["subject"] == "Re: lease renewal"
    assert m["thread_key"] == "lease renewal"
    assert m["message_id"] == "<abc123@example.com>"
    assert m["date_utc"] == "2026-08-05T12:02:00Z"
    assert "renew the lease" in m["body_text"]
    assert m["snippet"].startswith("Hi, do you want")
    assert json.loads(m["to_json"]) == ["me@example.com"]


def test_multipart_prefers_both_bodies():
    m = parse_rfc822(MULTIPART)
    assert "$12.99" in m["body_text"]
    assert "<b>$12.99</b>" in m["body_html"]


def test_html_sanitized():
    m = parse_rfc822(EVIL_HTML)
    assert "script" not in m["body_html"].lower()
    assert "alert(1)" not in m["body_html"]
    assert "onclick" not in m["body_html"]
    assert "<img" not in m["body_html"]
    assert 'href="https://ok.com"' in m["body_html"]
    # html-only mail still gets a text body for search/snippet
    assert "hi" in m["body_text"]


def test_encoded_words_and_missing_date():
    m = parse_rfc822(ENCODED)
    assert m["subject"] == "Grüße aus München"
    assert m["from_name"] == "Jürgen"
    assert m["date_utc"] == ""

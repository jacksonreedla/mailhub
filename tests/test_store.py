import pytest

import db
import store


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    return c


def parsed(subject="hello", body="world text", from_email="a@x.com",
           date="2026-08-05T10:00:00Z"):
    return {
        "message_id": f"<{subject}@x>",
        "thread_key": subject.casefold(),
        "from_name": "A",
        "from_email": from_email,
        "to_json": '["me@x.com"]',
        "date_utc": date,
        "subject": subject,
        "body_text": body,
        "body_html": "",
        "snippet": body[:160],
    }


def test_upsert_dedupes_on_uid(conn):
    acct = store.upsert_account(conn, "a@x.com", "gmail")
    store.upsert_message(conn, acct, "INBOX", 1, parsed())
    store.upsert_message(conn, acct, "INBOX", 1, parsed())
    assert len(store.list_messages(conn)) == 1


def test_list_merges_accounts_newest_first(conn):
    a1 = store.upsert_account(conn, "a@x.com", "gmail")
    a2 = store.upsert_account(conn, "b@y.com", "gmail")
    store.upsert_message(conn, a1, "INBOX", 1,
                         parsed("older", date="2026-08-01T00:00:00Z"))
    store.upsert_message(conn, a2, "INBOX", 1,
                         parsed("newer", date="2026-08-05T00:00:00Z"))
    msgs = store.list_messages(conn)
    assert [m["subject"] for m in msgs] == ["newer", "older"]
    assert msgs[0]["account_email"] == "b@y.com"


def test_list_filters_by_account(conn):
    a1 = store.upsert_account(conn, "a@x.com", "gmail")
    a2 = store.upsert_account(conn, "b@y.com", "gmail")
    store.upsert_message(conn, a1, "INBOX", 1, parsed("mine"))
    store.upsert_message(conn, a2, "INBOX", 1, parsed("theirs"))
    msgs = store.list_messages(conn, account_id=a1)
    assert [m["subject"] for m in msgs] == ["mine"]


def test_search_subject_and_body(conn):
    acct = store.upsert_account(conn, "a@x.com", "gmail")
    store.upsert_message(conn, acct, "INBOX", 1,
                         parsed("quarterly zebra report", "nothing"))
    store.upsert_message(conn, acct, "INBOX", 2,
                         parsed("boring", "the walrus arrives tuesday"))
    assert [m["subject"] for m in store.search_messages(conn, "zebra")] == \
        ["quarterly zebra report"]
    assert [m["subject"] for m in store.search_messages(conn, "walrus")] == \
        ["boring"]


def test_search_survives_quotes_and_operators(conn):
    acct = store.upsert_account(conn, "a@x.com", "gmail")
    store.upsert_message(conn, acct, "INBOX", 1, parsed("hello"))
    # none of these may raise
    store.search_messages(conn, 'he said "hello"')
    store.search_messages(conn, "AND OR NOT (")
    store.search_messages(conn, "")


def test_get_and_mark_read(conn):
    acct = store.upsert_account(conn, "a@x.com", "gmail")
    mid = store.upsert_message(conn, acct, "INBOX", 1, parsed())
    msg = store.get_message(conn, mid)
    assert msg["subject"] == "hello"
    assert msg["is_read"] == 0
    store.mark_read(conn, mid)
    assert store.get_message(conn, mid)["is_read"] == 1
    assert store.get_message(conn, 999999) is None


def test_sync_state_roundtrip(conn):
    acct = store.upsert_account(conn, "a@x.com", "gmail")
    assert store.get_sync_state(conn, acct, "INBOX") is None
    store.set_sync_state(conn, acct, "INBOX", uidvalidity=42, last_uid=100)
    assert store.get_sync_state(conn, acct, "INBOX") == (42, 100)
    store.set_sync_state(conn, acct, "INBOX", uidvalidity=42, last_uid=150)
    assert store.get_sync_state(conn, acct, "INBOX") == (42, 150)

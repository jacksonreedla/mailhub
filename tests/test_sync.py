import pytest

import db
import store
import sync
from accounts import Account
from fakes import FakeIMAPClient


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    return c


ACCOUNT = Account(email="me@gmail.com", provider="gmail",
                  imap_host="imap.gmail.com", username="me@gmail.com",
                  password="app-pass")


def raw(subject, n):
    return (f"From: s{n}@example.com\r\n"
            f"To: me@gmail.com\r\n"
            f"Subject: {subject}\r\n"
            f"Message-ID: <m{n}@example.com>\r\n"
            f"Date: Wed, 05 Aug 2026 10:{n:02d}:00 +0000\r\n"
            f"Content-Type: text/plain\r\n\r\n"
            f"body {n}\r\n").encode()


def test_first_sync_ingests_all(conn):
    client = FakeIMAPClient({1: raw("one", 1), 2: raw("two", 2)})
    n = sync.sync_account(conn, ACCOUNT, client=client)
    assert n == 2
    assert len(store.list_messages(conn)) == 2
    acct_id = store.upsert_account(conn, ACCOUNT.email, ACCOUNT.provider)
    assert store.get_sync_state(conn, acct_id, "INBOX") == (1, 2)


def test_second_sync_is_noop(conn):
    client = FakeIMAPClient({1: raw("one", 1)})
    assert sync.sync_account(conn, ACCOUNT, client=client) == 1
    assert sync.sync_account(conn, ACCOUNT, client=client) == 0
    assert len(store.list_messages(conn)) == 1


def test_new_message_picked_up(conn):
    client = FakeIMAPClient({1: raw("one", 1)})
    sync.sync_account(conn, ACCOUNT, client=client)
    client.messages[2] = raw("two", 2)
    assert sync.sync_account(conn, ACCOUNT, client=client) == 1
    subjects = {m["subject"] for m in store.list_messages(conn)}
    assert subjects == {"one", "two"}


def test_uidvalidity_change_wipes_and_resyncs(conn):
    client = FakeIMAPClient({1: raw("one", 1)}, uidvalidity=1)
    sync.sync_account(conn, ACCOUNT, client=client)
    # server renumbered: same mail now uid 50, new validity
    client.messages = {50: raw("one-renumbered", 1)}
    client.uidvalidity = 2
    sync.sync_account(conn, ACCOUNT, client=client)
    msgs = store.list_messages(conn)
    assert [m["subject"] for m in msgs] == ["one-renumbered"]


def test_fetch_failure_keeps_earlier_batches(conn):
    msgs = {i: raw(f"m{i}", i) for i in range(1, 6)}
    client = FakeIMAPClient(msgs)
    client.fail_on_fetch_uids = {4}
    with pytest.raises(ConnectionError):
        sync.sync_account(conn, ACCOUNT, client=client, batch=2)
    # first batch (uids 1,2) persisted with state advanced
    stored = store.list_messages(conn)
    assert len(stored) == 2
    acct_id = store.upsert_account(conn, ACCOUNT.email, ACCOUNT.provider)
    assert store.get_sync_state(conn, acct_id, "INBOX") == (1, 2)
    # retry after failure resumes and completes
    client.fail_on_fetch_uids = set()
    assert sync.sync_account(conn, ACCOUNT, client=client, batch=2) == 3
    assert len(store.list_messages(conn)) == 5


def test_first_sync_caps_backlog(conn):
    msgs = {i: raw(f"m{i}", i % 60) for i in range(1, 301)}
    client = FakeIMAPClient(msgs)
    n = sync.sync_account(conn, ACCOUNT, client=client, initial_limit=200)
    assert n == 200
    uids = sorted(m["uid"] for m in store.list_messages(conn, limit=1000))
    assert uids[0] == 101 and uids[-1] == 300

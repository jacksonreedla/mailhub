import db
import store
import sync
from accounts import Account
from tests.fakes import FakeIMAPClient

ACCOUNT = Account(email="x@y.com", provider="gmail",
                  imap_host="imap.gmail.com", username="x@y.com",
                  password="p")

BULK = (b"From: Offers <offers@wish.com>\r\nTo: me@x.com\r\n"
        b"Subject: SALE\r\nList-Unsubscribe: <mailto:u@wish.com>\r\n"
        b"\r\nbuy")


def _conn(tmp_path):
    c = db.connect(tmp_path / "m.db")
    db.init_db(c)
    return c


def test_synced_message_gets_lane(tmp_path):
    conn = _conn(tmp_path)
    client = FakeIMAPClient({1: BULK})
    sync.sync_account(conn, ACCOUNT, client=client)
    assert len(store.list_messages(conn, lane="newsletters")) == 1


def test_user_rule_applies_during_sync(tmp_path):
    conn = _conn(tmp_path)
    store.add_rule(conn, "from_domain", "wish.com", "people")
    client = FakeIMAPClient({1: BULK})
    sync.sync_account(conn, ACCOUNT, client=client)
    assert len(store.list_messages(conn, lane="people")) == 1

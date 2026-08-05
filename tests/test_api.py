import pytest

import db
import store
from app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "t.db"
    conn = db.connect(db_path)
    db.init_db(conn)
    a1 = store.upsert_account(conn, "a@gmail.com", "gmail")
    a2 = store.upsert_account(conn, "b@gmail.com", "gmail")
    store.upsert_message(conn, a1, "INBOX", 1, {
        "message_id": "<m1@x>", "thread_key": "lease", "from_name": "Sarah",
        "from_email": "sarah@x.com", "to_json": '["a@gmail.com"]',
        "date_utc": "2026-08-05T14:02:00Z", "subject": "Re: lease renewal",
        "body_text": "renew by friday", "body_html": "<p>renew by friday</p>",
        "snippet": "renew by friday",
    })
    store.upsert_message(conn, a2, "INBOX", 1, {
        "message_id": "<m2@x>", "thread_key": "receipt", "from_name": "Stripe",
        "from_email": "billing@stripe.com", "to_json": '["b@gmail.com"]',
        "date_utc": "2026-08-05T13:40:00Z", "subject": "Receipt #4821",
        "body_text": "total 12.99", "body_html": "",
        "snippet": "total 12.99",
    })
    conn.close()
    app = create_app(db_path=db_path)
    app.testing = True
    return app.test_client()


def test_list_merges_accounts(client):
    r = client.get("/api/messages")
    assert r.status_code == 200
    msgs = r.get_json()["messages"]
    assert [m["subject"] for m in msgs] == ["Re: lease renewal",
                                            "Receipt #4821"]
    assert msgs[0]["account_email"] == "a@gmail.com"


def test_list_filters_by_account(client):
    accts = client.get("/api/accounts").get_json()["accounts"]
    a2 = next(a for a in accts if a["email"] == "b@gmail.com")
    msgs = client.get(f"/api/messages?account={a2['id']}").get_json()["messages"]
    assert [m["subject"] for m in msgs] == ["Receipt #4821"]


def test_search(client):
    msgs = client.get("/api/messages?q=lease").get_json()["messages"]
    assert [m["subject"] for m in msgs] == ["Re: lease renewal"]


def test_get_message_full(client):
    mid = client.get("/api/messages").get_json()["messages"][0]["id"]
    m = client.get(f"/api/messages/{mid}").get_json()
    assert m["body_html"] == "<p>renew by friday</p>"
    assert m["body_text"] == "renew by friday"


def test_get_unknown_404(client):
    assert client.get("/api/messages/99999").status_code == 404


def test_mark_read(client):
    mid = client.get("/api/messages").get_json()["messages"][0]["id"]
    r = client.post(f"/api/messages/{mid}/read", json={"read": True})
    assert r.status_code == 200
    assert client.get(f"/api/messages/{mid}").get_json()["is_read"] == 1


def test_accounts_with_counts(client):
    accts = client.get("/api/accounts").get_json()["accounts"]
    assert {a["email"]: a["message_count"] for a in accts} == {
        "a@gmail.com": 1, "b@gmail.com": 1}


def test_status_without_daemon(client):
    s = client.get("/api/status").get_json()
    assert s["daemon"] == "off"


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Mailhub" in r.data or b"MAILHUB" in r.data

import db
import store
from app import create_app


def _client(tmp_path):
    app = create_app(db_path=tmp_path / "m.db")
    return app.test_client()


def _seed(tmp_path):
    c = db.connect(tmp_path / "m.db")
    db.init_db(c)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, {
        "message_id": "", "thread_key": "", "from_name": "",
        "from_email": "offers@wish.com", "to_json": "[]",
        "date_utc": "2026-08-18T00:00:00Z", "subject": "sale",
        "body_text": "b", "body_html": "", "snippet": "b",
        "is_bulk": 1, "lane": "newsletters"})
    c.close()


def test_lane_filter(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    assert len(cl.get("/api/messages?lane=newsletters").json["messages"]) == 1
    assert cl.get("/api/messages?lane=people").json["messages"] == []


def test_lane_counts_endpoint(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    lanes = cl.get("/api/lanes").json["lanes"]
    assert lanes["newsletters"]["total"] == 1


def test_rules_crud_reclassifies(tmp_path):
    _seed(tmp_path)
    cl = _client(tmp_path)
    r = cl.post("/api/rules", json={"field": "from_domain",
                                    "pattern": "wish.com", "lane": "people"})
    assert r.status_code == 200
    rid = r.json["id"]
    assert len(cl.get("/api/messages?lane=people").json["messages"]) == 1
    assert cl.post("/api/rules", json={"field": "nope", "pattern": "x",
                                       "lane": "people"}).status_code == 400
    assert cl.delete(f"/api/rules/{rid}").json["ok"] is True
    assert cl.get("/api/messages?lane=people").json["messages"] == []

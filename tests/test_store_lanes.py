import pytest

import db
import store


def _conn(tmp_path):
    c = db.connect(tmp_path / "m.db")
    db.init_db(c)
    return c


def _msg(**kw):
    base = {"message_id": "", "thread_key": "", "from_name": "",
            "from_email": "offers@wish.com", "to_json": "[]",
            "date_utc": "2026-08-18T00:00:00Z", "subject": "sale",
            "body_text": "b", "body_html": "", "snippet": "b",
            "is_bulk": 1, "lane": "newsletters"}
    base.update(kw)
    return base


def test_upsert_stores_lane_and_bulk(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    mid = store.upsert_message(c, a, "INBOX", 1, _msg())
    row = store.get_message(c, mid)
    assert row["lane"] == "newsletters"


def test_list_messages_lane_filter(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())
    store.upsert_message(c, a, "INBOX", 2,
                         _msg(from_email="liz@example.org", lane="people"))
    out = store.list_messages(c, lane="people")
    assert [m["from_email"] for m in out] == ["liz@example.org"]


def test_lane_counts(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())
    counts = store.lane_counts(c)
    assert counts["newsletters"]["total"] == 1
    assert counts["newsletters"]["unread"] == 1
    assert counts["people"]["total"] == 0


def test_rules_crud_and_validation(tmp_path):
    c = _conn(tmp_path)
    rid = store.add_rule(c, "from_domain", "twitter.com", "people")
    assert [r["id"] for r in store.list_rules(c)] == [rid]
    with pytest.raises(ValueError):
        store.add_rule(c, "bogus_field", "x", "people")
    with pytest.raises(ValueError):
        store.add_rule(c, "subject", "x", "bogus_lane")
    with pytest.raises(ValueError):
        store.add_rule(c, "subject", "  ", "people")
    store.delete_rule(c, rid)
    assert store.list_rules(c) == []


def test_reclassify_all_applies_new_rule(tmp_path):
    c = _conn(tmp_path)
    a = store.upsert_account(c, "x@y.com", "gmail")
    store.upsert_message(c, a, "INBOX", 1, _msg())  # newsletters
    store.add_rule(c, "from_domain", "wish.com", "people")
    changed = store.reclassify_all(c)
    assert changed == 1
    assert store.list_messages(c, lane="people")[0]["from_email"] == "offers@wish.com"

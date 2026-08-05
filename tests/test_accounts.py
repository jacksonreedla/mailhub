import json

import pytest

import accounts


def write_creds(tmp_path, payload):
    p = tmp_path / "credentials.json"
    p.write_text(json.dumps(payload) if isinstance(payload, dict) else payload)
    return p


def test_gmail_defaults(tmp_path):
    p = write_creds(tmp_path, {"accounts": [
        {"email": "me@gmail.com", "provider": "gmail", "password": "apppass"}
    ]})
    accts = accounts.load_accounts(p)
    assert len(accts) == 1
    a = accts[0]
    assert a.email == "me@gmail.com"
    assert a.imap_host == "imap.gmail.com"
    assert a.username == "me@gmail.com"
    assert a.password == "apppass"


def test_explicit_imap_overrides(tmp_path):
    p = write_creds(tmp_path, {"accounts": [
        {"email": "me@fastmail.com", "provider": "imap",
         "imap_host": "imap.fastmail.com", "username": "me@fastmail.com",
         "password": "x", "display_name": "FM"}
    ]})
    a = accounts.load_accounts(p)[0]
    assert a.imap_host == "imap.fastmail.com"
    assert a.display_name == "FM"


def test_missing_file_is_empty(tmp_path):
    assert accounts.load_accounts(tmp_path / "nope.json") == []


def test_malformed_json_raises_without_leaking(tmp_path):
    p = write_creds(tmp_path, '{"accounts": [ {"password": "supersecret"')
    with pytest.raises(ValueError) as e:
        accounts.load_accounts(p)
    assert "credentials.json" in str(e.value)
    assert "supersecret" not in str(e.value)


def test_entry_missing_email_raises(tmp_path):
    p = write_creds(tmp_path, {"accounts": [{"provider": "gmail",
                                             "password": "y"}]})
    with pytest.raises(ValueError):
        accounts.load_accounts(p)

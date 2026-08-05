"""Account registry: reads ~/.mailhub/credentials.json (never in the repo)."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".mailhub"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"

PROVIDER_IMAP_HOSTS = {
    "gmail": "imap.gmail.com",
}


@dataclass
class Account:
    email: str
    provider: str
    imap_host: str
    username: str
    password: str
    display_name: str = ""


def ensure_config_dir():
    CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
    return CONFIG_DIR


def load_accounts(path=None):
    path = Path(path) if path else CREDENTIALS_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"credentials.json is not valid JSON ({path.name}, line {e.lineno})"
        ) from None
    accts = []
    for entry in data.get("accounts", []):
        email = entry.get("email")
        if not email:
            raise ValueError("credentials.json: account entry missing 'email'")
        provider = entry.get("provider", "imap")
        imap_host = entry.get("imap_host") or PROVIDER_IMAP_HOSTS.get(provider)
        if not imap_host:
            raise ValueError(
                f"credentials.json: account {email} needs an 'imap_host'"
            )
        accts.append(Account(
            email=email,
            provider=provider,
            imap_host=imap_host,
            username=entry.get("username", email),
            password=entry.get("password", ""),
            display_name=entry.get("display_name", ""),
        ))
    return accts

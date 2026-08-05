"""Incremental IMAP sync: read-only, UID-tracked, crash-safe per batch."""

import sys
import threading
import traceback

import imapclient

import db
import store
from mailparse import parse_rfc822

DEFAULT_FOLDER = "INBOX"


def _make_client(account):
    client = imapclient.IMAPClient(account.imap_host, ssl=True)
    client.login(account.username, account.password)
    return client


def sync_account(conn, account, client=None, folder=DEFAULT_FOLDER,
                 batch=50, initial_limit=200):
    """Sync one account's folder. Returns number of new messages stored."""
    own_client = client is None
    if own_client:
        client = _make_client(account)
    try:
        acct_id = store.upsert_account(conn, account.email, account.provider,
                                       account.display_name)
        info = client.select_folder(folder, readonly=True)
        uidvalidity = int(info.get(b"UIDVALIDITY", info.get("UIDVALIDITY", 0)))

        state = store.get_sync_state(conn, acct_id, folder)
        if state is not None and state[0] != uidvalidity:
            # server renumbered UIDs — local copy is unreliable, start over
            store.delete_account_messages(conn, acct_id, folder)
            state = None

        if state is None:
            uids = sorted(client.search("ALL"))[-initial_limit:]
            last_uid = 0
        else:
            last_uid = state[1]
            uids = [u for u in client.search(["UID", f"{last_uid + 1}:*"])
                    if u > last_uid]
            uids.sort()

        stored = 0
        for i in range(0, len(uids), batch):
            chunk = uids[i:i + batch]
            fetched = client.fetch(chunk, ["RFC822"])
            for uid in chunk:
                data = fetched.get(uid)
                if not data:
                    continue
                raw = data.get(b"RFC822") or data.get("RFC822")
                if raw is None:
                    continue
                store.upsert_message(conn, acct_id, folder, uid,
                                     parse_rfc822(raw))
                stored += 1
            # advance state after every batch so a crash never refetches
            store.set_sync_state(conn, acct_id, folder, uidvalidity, chunk[-1])
        if not uids:
            store.set_sync_state(conn, acct_id, folder, uidvalidity, last_uid)
        return stored
    finally:
        if own_client:
            try:
                client.logout()
            except Exception:
                pass


class SyncDaemon:
    """Background loop syncing every account on an interval."""

    def __init__(self, db_path, accounts, interval=180):
        self.db_path = db_path
        self.accounts = accounts
        self.interval = interval
        self.status = {}  # email -> {"ok": bool, "detail": str}
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="mailhub-sync")

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def trigger(self):
        """Request an immediate pass."""
        self._wake.set()

    def is_alive(self):
        return self._thread.is_alive()

    def _run(self):
        conn = db.connect(self.db_path)
        db.init_db(conn)
        while not self._stop.is_set():
            for account in self.accounts:
                if self._stop.is_set():
                    break
                try:
                    n = sync_account(conn, account)
                    self.status[account.email] = {"ok": True,
                                                  "detail": f"+{n}"}
                except Exception as e:
                    # one bad account must never kill the loop
                    self.status[account.email] = {"ok": False,
                                                  "detail": str(e)}
                    traceback.print_exc(file=sys.stderr)
            self._wake.wait(timeout=self.interval)
            self._wake.clear()

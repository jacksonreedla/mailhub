"""In-memory stand-in for imapclient.IMAPClient used by sync tests."""


class FakeIMAPClient:
    def __init__(self, messages=None, uidvalidity=1):
        # {uid: raw_rfc822_bytes}
        self.messages = dict(messages or {})
        self.uidvalidity = uidvalidity
        self.fail_on_fetch_uids = set()
        self.logged_out = False

    def select_folder(self, folder, readonly=False):
        assert readonly, "sync must open folders read-only"
        return {b"UIDVALIDITY": self.uidvalidity,
                b"EXISTS": len(self.messages)}

    def search(self, criteria):
        uids = sorted(self.messages)
        if criteria == "ALL" or criteria == ["ALL"]:
            return uids
        # ['UID', 'n:*'] form
        if isinstance(criteria, (list, tuple)) and criteria[0] == "UID":
            start = int(str(criteria[1]).split(":")[0])
            return [u for u in uids if u >= start]
        raise AssertionError(f"unexpected criteria {criteria!r}")

    def fetch(self, uids, parts):
        out = {}
        for uid in uids:
            if uid in self.fail_on_fetch_uids:
                raise ConnectionError("fake fetch failure")
            if uid in self.messages:
                out[uid] = {b"RFC822": self.messages[uid]}
        return out

    def logout(self):
        self.logged_out = True

from mailparse import parse_rfc822

BULK = (b"From: Offers <offers@shop.com>\r\nTo: me@x.com\r\n"
        b"Subject: SALE\r\nList-Unsubscribe: <mailto:u@shop.com>\r\n"
        b"\r\nbuy things")
LISTID = (b"From: List <l@groups.io>\r\nTo: me@x.com\r\n"
          b"Subject: digest\r\nList-Id: <cool.groups.io>\r\n"
          b"\r\nhi all")
PLAIN = (b"From: Liz <liz@example.org>\r\nTo: me@x.com\r\n"
         b"Subject: hi\r\n\r\nhello")


def test_list_unsubscribe_marks_bulk():
    assert parse_rfc822(BULK)["is_bulk"] == 1


def test_list_id_marks_bulk():
    assert parse_rfc822(LISTID)["is_bulk"] == 1


def test_plain_mail_not_bulk():
    assert parse_rfc822(PLAIN)["is_bulk"] == 0

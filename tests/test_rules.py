import rules


def m(from_email="a@b.com", subject="hi", is_bulk=0):
    return {"from_email": from_email, "subject": subject, "is_bulk": is_bulk}


def test_receipt_subject():
    assert rules.classify(m(subject="Your receipt #4821 from Stripe")) == "receipts"


def test_order_confirmation():
    assert rules.classify(m(subject="Order Confirmation - eBay", is_bulk=1)) == "receipts"


def test_social_domain_is_notification():
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1)) == "notifications"


def test_noreply_localpart_is_notification():
    assert rules.classify(m(from_email="no-reply@somesite.io")) == "notifications"


def test_bulk_header_is_newsletter():
    assert rules.classify(m(from_email="olly@storylearning.com", is_bulk=1)) == "newsletters"


def test_marketing_localpart_is_newsletter():
    assert rules.classify(m(from_email="offers@wish.com")) == "newsletters"


def test_plain_human_is_people():
    assert rules.classify(m(from_email="liz.beard@villeplatterotary.org")) == "people"


def test_user_rule_wins_over_heuristics():
    r = [{"field": "from_domain", "pattern": "twitter.com",
          "lane": "people", "enabled": 1}]
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1), r) == "people"


def test_disabled_rule_ignored():
    r = [{"field": "from_domain", "pattern": "twitter.com",
          "lane": "people", "enabled": 0}]
    assert rules.classify(m(from_email="info@twitter.com", is_bulk=1), r) == "notifications"


def test_subject_rule_substring_case_insensitive():
    r = [{"field": "subject", "pattern": "OMNICHROME",
          "lane": "people", "enabled": 1}]
    assert rules.classify(m(subject="omnichrome invoice", is_bulk=1), r) == "people"


def test_missing_fields_tolerated():
    assert rules.classify({}) == "people"

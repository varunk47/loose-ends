"""The vendor directory is the offline brain: it classifies known senders without a model
and drafts template notices, so the demo runs with no credentials at all."""

from datetime import date

from loose_ends.correspondence import Notice
from loose_ends.discovery import Message
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import Account, Estate
from loose_ends.vendors import VendorDirectory, rule_classifier, template_notice


def test_directory_knows_the_demo_vendors():
    directory = VendorDirectory.load()

    netflix = directory.lookup("netflix.com")
    assert netflix.vendor == "Netflix" and netflix.category == "subscription"
    assert directory.lookup("nobody.example") is None


def test_rule_classifier_marks_known_accounts_and_ignores_noise():
    classify = rule_classifier(VendorDirectory.load())
    messages = [
        Message(id="a", sender="info@mailer.netflix.com", date=date(2026, 7, 1), subject="Your bill", body="$15.49"),
        Message(id="b", sender="ada@gmail.com", date=date(2026, 7, 2), subject="Photos", body="love"),
        Message(id="c", sender="deals@unknownshop.example", date=date(2026, 7, 3), subject="SALE", body=""),
    ]

    signals = {s.message_id: s for s in classify(messages)}

    assert signals["a"].is_account and signals["a"].category == "subscription"
    assert signals["a"].amount == 15.49 and signals["a"].cadence == "monthly"
    assert not signals["b"].is_account
    assert not signals["c"].is_account and signals["c"].confidence < 0.5


def test_template_notice_names_the_executor_and_never_the_deceased_as_sender():
    estate = Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
                    executor_email="priya@example.com", state="IL")
    account = Account(vendor="Netflix", domain="netflix.com", category="subscription")

    notice = template_notice(estate, account, load_playbooks()["subscription"])

    assert isinstance(notice, Notice)
    assert "Raymond Okafor" in notice.subject
    assert "on behalf of Priya Okafor" in notice.body
    assert "cancel" in notice.body.lower()
    assert "death certificate" in notice.body.lower()

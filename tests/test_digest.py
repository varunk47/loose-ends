"""The digest is the one email a day: at most three decisions, plus the counts."""

from datetime import date

from loose_ends.digest import compose_digest, send_digest
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.schema import Account, AccountStatus, Decision, Estate


def test_digest_carries_at_most_three_decisions_and_the_counts(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com", state="IL"))
    done = ledger.upsert_account(estate.id, Account(vendor="Netflix", domain="netflix.com", category="subscription"))
    ledger.set_status(estate.id, done.id, AccountStatus.DONE)
    for i in range(4):
        acc = ledger.upsert_account(estate.id, Account(vendor=f"Vendor {i}", domain=f"v{i}.com", category="utility"))
        ledger.set_status(estate.id, acc.id, AccountStatus.AWAITING_DECISION)
        ledger.add_decision(estate.id, Decision(account_id=acc.id, question=f"Question {i}?",
                                                options=["a", "b"], resumes_action="choose"))

    digest = compose_digest(ledger, estate.id)

    assert len(digest.decisions) == 3
    assert digest.counts["done"] == 1 and digest.counts["awaiting_decision"] == 4
    assert "Question 0?" in digest.body and "Question 3?" not in digest.body
    assert "1 more" in digest.body


def test_send_digest_goes_to_the_executor(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com", state="IL"))
    mailer = OutboxMailer(tmp_path / "mail")

    mail = send_digest(mailer, estate, compose_digest(ledger, estate.id))

    assert mail.to == "priya@example.com"
    assert "Loose Ends" in mail.subject

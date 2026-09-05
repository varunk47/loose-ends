"""The digest says "reply with the number and your choice". A reply from the executor's
address with "2 transfer" answers the second open decision."""

from datetime import date

from loose_ends.brain import Brain
from loose_ends.digest import compose_digest
from loose_ends.followup import follow_up
from loose_ends.ledger import JsonLedger
from loose_ends.mail import IncomingMail, OutboxMailer
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import Account, AccountStatus, Decision, Estate


def make_world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com", state="IL"))
    for vendor in ["ComEd", "Nicor Gas", "Xfinity"]:
        acc = ledger.upsert_account(estate.id, Account(vendor=vendor, domain=f"{vendor.lower().replace(' ', '')}.com",
                                                       category="utility", status=AccountStatus.AWAITING_DECISION))
        ledger.add_decision(estate.id, Decision(account_id=acc.id, question=f"{vendor}: transfer or close?",
                                                options=["transfer", "close"], resumes_action="transfer_or_close"))
    return ledger, estate, OutboxMailer(tmp_path / "mail")


def test_numbered_reply_from_the_executor_answers_that_decision(tmp_path):
    ledger, estate, mailer = make_world(tmp_path)
    digest = compose_digest(ledger, estate.id)
    assert digest.decisions[1].question.startswith("Nicor Gas")
    mailer.drop_reply(IncomingMail(id="r1", sender="priya@example.com", date=date(2026, 8, 11),
                                   subject="Re: " + digest.subject, body="2 transfer\n\nThanks"))

    report = follow_up(ledger, mailer, Brain.offline(), estate.id, load_playbooks(), today=date(2026, 8, 11))

    assert report.answers == 1
    answered = ledger.answered_decisions(estate.id)
    assert len(answered) == 1 and answered[0].question.startswith("Nicor Gas") and answered[0].answer == "transfer"


def test_reply_accepts_punctuation_and_option_prefixes(tmp_path):
    ledger, estate, mailer = make_world(tmp_path)
    mailer.drop_reply(IncomingMail(id="r2", sender="Priya Okafor <priya@example.com>", date=date(2026, 8, 11),
                                   subject="Re: Loose Ends", body="1. Close it please"))

    follow_up(ledger, mailer, Brain.offline(), estate.id, load_playbooks(), today=date(2026, 8, 11))

    answered = ledger.answered_decisions(estate.id)
    assert answered[0].question.startswith("ComEd") and answered[0].answer == "close"


def test_unparseable_or_foreign_replies_are_ignored(tmp_path):
    ledger, estate, mailer = make_world(tmp_path)
    mailer.drop_reply(IncomingMail(id="r3", sender="priya@example.com", date=date(2026, 8, 11),
                                   subject="Re: Loose Ends", body="Can we talk tomorrow?"))
    mailer.drop_reply(IncomingMail(id="r4", sender="stranger@example.com", date=date(2026, 8, 11),
                                   subject="Re: Loose Ends", body="1 close"))

    report = follow_up(ledger, mailer, Brain.offline(), estate.id, load_playbooks(), today=date(2026, 8, 11))

    assert report.answers == 0 and ledger.answered_decisions(estate.id) == []

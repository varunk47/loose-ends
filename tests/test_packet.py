"""The authority packet: certificate, executor ID, proof of authority. A playbook that needs
a piece the executor does not have yet becomes a question, not a half-baked notice."""

from datetime import date

from loose_ends.brain import Brain
from loose_ends.dispatch import dispatch
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate

TODAY = date(2026, 8, 10)


def make_world(tmp_path, packet):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com",
                                         state="IL", certificate_key="certs/r.pdf", packet=packet))
    books = load_playbooks()
    ledger.upsert_account(estate.id, plan_account(Account(vendor="Chase", domain="chase.com", category="bank"), books))
    ledger.upsert_account(estate.id, plan_account(Account(vendor="Netflix", domain="netflix.com", category="subscription"), books))
    return ledger, estate, OutboxMailer(tmp_path / "mail"), books


def test_missing_authority_proof_holds_the_bank_notice_but_not_the_subscription(tmp_path):
    ledger, estate, mailer, books = make_world(tmp_path, packet=["certificate"])

    report = dispatch(ledger, mailer, Brain.offline(), estate.id, books, today=TODAY)

    statuses = {a.vendor: a.status for a in ledger.list_accounts(estate.id)}
    assert statuses == {"Chase": AccountStatus.AWAITING_DECISION, "Netflix": AccountStatus.AWAITING_REPLY}
    assert report.sent == 1 and report.decisions == 1
    decision = ledger.open_decisions(estate.id)[0]
    assert decision.resumes_action == "provide_packet"
    assert "executor ID" in decision.question and "proof of authority" in decision.question
    assert decision.options == ["I have them", "park"]


def test_answering_i_have_them_adds_to_the_packet_and_sends_next_cycle(tmp_path):
    ledger, estate, mailer, books = make_world(tmp_path, packet=["certificate"])
    dispatch(ledger, mailer, Brain.offline(), estate.id, books, today=TODAY)
    decision = ledger.open_decisions(estate.id)[0]
    ledger.answer_decision(estate.id, decision.id, "I have them")

    report = dispatch(ledger, mailer, Brain.offline(), estate.id, books, today=date(2026, 8, 11))

    assert report.resumed == 1
    assert set(ledger.get_estate(estate.id).packet) == {"certificate", "executor_id", "authority_proof"}
    chase = next(a for a in ledger.list_accounts(estate.id) if a.vendor == "Chase")
    assert chase.status == AccountStatus.AWAITING_REPLY
    assert mailer.sent()[-1].to == "support@chase.com"


def test_complete_packet_sends_everything(tmp_path):
    ledger, estate, mailer, books = make_world(tmp_path, packet=["certificate", "executor_id", "authority_proof"])

    report = dispatch(ledger, mailer, Brain.offline(), estate.id, books, today=TODAY)

    assert report.sent == 2 and report.decisions == 0

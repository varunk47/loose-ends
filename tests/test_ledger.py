"""The ledger is the product: every account, decision and action lives here, and the
dashboard and the agents read and write the same records."""

from datetime import date

import pytest

from loose_ends.ledger import JsonLedger
from loose_ends.schema import Account, AccountStatus, Decision, Estate


@pytest.fixture
def ledger(tmp_path):
    return JsonLedger(tmp_path / "ledger")


@pytest.fixture
def estate(ledger):
    return ledger.create_estate(
        Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
               executor_name="Priya Okafor", executor_email="priya@example.com", state="IL")
    )


def test_estate_round_trips_through_disk(ledger, estate, tmp_path):
    reopened = JsonLedger(tmp_path / "ledger")

    assert reopened.get_estate(estate.id) == estate


def test_upsert_account_dedupes_by_vendor_domain_and_merges_evidence(ledger, estate):
    ledger.upsert_account(estate.id, Account(vendor="Netflix", domain="netflix.com",
                                              category="subscription", evidence=["m1"], confidence=0.6))
    ledger.upsert_account(estate.id, Account(vendor="Netflix", domain="netflix.com",
                                              category="subscription", evidence=["m2"], confidence=0.9))

    accounts = ledger.list_accounts(estate.id)

    assert len(accounts) == 1
    assert accounts[0].evidence == ["m1", "m2"]
    assert accounts[0].confidence == 0.9
    assert accounts[0].status == AccountStatus.DISCOVERED


def test_decision_can_be_answered_and_stops_being_open(ledger, estate):
    account = ledger.upsert_account(estate.id, Account(vendor="ComEd", domain="comed.com", category="utility"))
    decision = ledger.add_decision(estate.id, Decision(
        account_id=account.id, question="Transfer ComEd to Mom or close?",
        options=["transfer", "close"], resumes_action="transfer_or_close"))

    assert [d.id for d in ledger.open_decisions(estate.id)] == [decision.id]

    ledger.answer_decision(estate.id, decision.id, "transfer")

    assert ledger.open_decisions(estate.id) == []
    assert ledger.answered_decisions(estate.id)[0].answer == "transfer"


def test_actions_are_appended_in_order_with_artifacts(ledger, estate):
    account = ledger.upsert_account(estate.id, Account(vendor="Netflix", domain="netflix.com", category="subscription"))
    ledger.log_action(estate.id, account.id, type="email", payload={"to": "help@netflix.com"},
                      result="sent", artifacts=["s3://x/notice.eml"])
    ledger.log_action(estate.id, account.id, type="email", payload={}, result="reply_closed")

    actions = ledger.list_actions(estate.id, account_id=account.id)

    assert [a.result for a in actions] == ["sent", "reply_closed"]
    assert actions[0].artifacts == ["s3://x/notice.eml"]


def test_set_status_updates_only_that_account(ledger, estate):
    a = ledger.upsert_account(estate.id, Account(vendor="Netflix", domain="netflix.com", category="subscription"))
    b = ledger.upsert_account(estate.id, Account(vendor="ComEd", domain="comed.com", category="utility"))

    ledger.set_status(estate.id, a.id, AccountStatus.SENT)

    statuses = {acc.vendor: acc.status for acc in ledger.list_accounts(estate.id)}
    assert statuses == {"Netflix": AccountStatus.SENT, "ComEd": AccountStatus.DISCOVERED}
    assert b.status == AccountStatus.DISCOVERED

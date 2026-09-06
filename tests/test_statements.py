"""A bank or card statement export is the second discovery channel: recurring debits become
messages the same pipeline can classify, so merchants that never email still get found."""

from datetime import date
from pathlib import Path

from loose_ends.discovery import Message
from loose_ends.statements import load_statement_csv
from loose_ends.vendors import VendorDirectory, rule_classifier

FIXTURE = Path(__file__).parent / "fixtures" / "statement_small.csv"


def test_recurring_debits_become_messages_and_one_offs_and_credits_do_not():
    messages = load_statement_csv(FIXTURE, VendorDirectory.load())

    senders = sorted({m.sender for m in messages})
    assert senders == ["billing@hulu.statement", "billing@lawnpros.statement", "billing@netflix.com"]
    assert len(messages) == 6
    netflix = next(m for m in messages if m.sender_domain == "netflix.com" and m.date == date(2026, 7, 3))
    assert "15.49" in netflix.body and "NETFLIX.COM" in netflix.body
    assert netflix.id.startswith("stmt-") and netflix.sender_name == "Netflix"


def test_statement_ids_are_stable_across_loads():
    first = [m.id for m in load_statement_csv(FIXTURE, VendorDirectory.load())]
    second = [m.id for m in load_statement_csv(FIXTURE, VendorDirectory.load())]

    assert first == second


def test_rule_classifier_treats_unknown_statement_merchants_as_recurring_accounts():
    classify = rule_classifier(VendorDirectory.load())
    hulu = Message(id="s1", sender="billing@hulu.statement", sender_name="Hulu", date=date(2026, 7, 5),
                   subject="Recurring charge: HULU", body="HULU 877-485-8411 CA charged $17.99 on 2026-07-05")

    signal = classify([hulu])[0]

    assert signal.is_account and signal.category == "subscription"
    assert signal.amount == 17.99 and signal.cadence == "monthly" and signal.vendor == "Hulu"

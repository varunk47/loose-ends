"""Discovery turns a pile of messages into ledger accounts with evidence. Classification
is a model call; aggregation is pure code and is tested without a model."""

from pathlib import Path

from loose_ends.discovery import (
    BatchSignals,
    MessageSignal,
    aggregate_signals,
    build_classifier,
    load_json_mailbox,
)
from loose_ends.models.fake import FakeModel

FIXTURE = Path(__file__).parent / "fixtures" / "inbox_small.json"


def test_json_mailbox_loads_messages_in_date_order():
    messages = load_json_mailbox(FIXTURE)

    assert [m.id for m in messages] == ["m2", "m1", "m3", "m4", "m5", "m6"]
    assert messages[0].sender_domain == "netflix.com"


def test_sender_domain_strips_mailer_subdomains():
    messages = {m.id: m for m in load_json_mailbox(FIXTURE)}

    assert messages["m1"].sender_domain == "netflix.com"
    assert messages["m5"].sender_domain == "chicagotribune.com"


def test_aggregate_groups_by_domain_and_drops_non_accounts():
    signals = [
        MessageSignal(message_id="m1", vendor="Netflix", domain="netflix.com", category="subscription",
                      signal="billing", is_account=True, confidence=0.9, amount=15.49, cadence="monthly"),
        MessageSignal(message_id="m2", vendor="Netflix", domain="netflix.com", category="subscription",
                      signal="billing", is_account=True, confidence=0.7, amount=15.49, cadence="monthly"),
        MessageSignal(message_id="m3", vendor="ComEd", domain="comed.com", category="utility",
                      signal="statement", is_account=True, confidence=0.95, amount=142.17),
        MessageSignal(message_id="m4", vendor="Ada Okafor", domain="gmail.com", category="personal",
                      signal="personal", is_account=False, confidence=0.99),
        MessageSignal(message_id="m5", vendor="Chicago Tribune", domain="chicagotribune.com",
                      category="marketing", signal="newsletter", is_account=False, confidence=0.8),
    ]

    accounts = aggregate_signals(signals)

    by_domain = {a.domain: a for a in accounts}
    assert set(by_domain) == {"netflix.com", "comed.com"}
    assert by_domain["netflix.com"].evidence == ["m1", "m2"]
    assert by_domain["netflix.com"].confidence == 0.9
    assert by_domain["netflix.com"].monthly_amount == 15.49
    assert by_domain["comed.com"].category == "utility"


def test_classifier_sends_subjects_to_the_model_and_returns_signals():
    model = FakeModel(structured=lambda prompt: BatchSignals(signals=[
        MessageSignal(message_id="m3", vendor="ComEd", domain="comed.com", category="utility",
                      signal="statement", is_account=True, confidence=0.9)
    ]))
    classify = build_classifier(model)
    messages = [m for m in load_json_mailbox(FIXTURE) if m.id == "m3"]

    signals = classify(messages)

    assert signals[0].domain == "comed.com"
    assert "Your ComEd statement is ready" in model.last_user_text
    assert "m3" in model.last_user_text

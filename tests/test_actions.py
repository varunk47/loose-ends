"""The vendor-action agent handles channels email cannot: web forms and phone calls. Its
irreversible tools are gated by a Strands HumanInTheLoop intervention whose approval is
deferred into the ledger, so a background run never blocks and the executor's answer on
a later cycle lets the tool run."""

from datetime import date

import pytest

from loose_ends.actions import act_on_account
from loose_ends.ledger import JsonLedger
from loose_ends.models.fake import FakeModel
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate

TODAY = date(2026, 8, 10)


@pytest.fixture
def world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=date(2026, 8, 3),
                                         executor_name="Priya Okafor", executor_email="priya@example.com", state="IL"))
    books = load_playbooks()
    facebook = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Facebook", domain="facebook.com", category="social_facebook", evidence=["m9"]), books))
    return ledger, estate, facebook, books


def form_model():
    def calls(prompt, tools):
        return [("submit_form", {"url": "https://www.facebook.com/help/contact/234739086860192",
                                 "fields": {"name": "Raymond Okafor", "request": "memorialize"}})] if "submit_form" in tools else []
    return FakeModel(text="Submitted the memorialization request.", tool_calls=calls)


def test_irreversible_tool_is_deferred_into_a_decision_not_run(world):
    ledger, estate, facebook, books = world

    report = act_on_account(ledger, form_model(), estate, facebook, books["social_facebook"], TODAY)

    assert report.deferred == 1 and report.executed == 0
    decision = ledger.open_decisions(estate.id)[0]
    assert decision.account_id == facebook.id and decision.resumes_action == "approve_tool"
    assert decision.context == "submit_form" and decision.options == ["approve", "park"]
    assert "Facebook" in decision.question and "facebook.com/help" in decision.question
    assert ledger.get_account(estate.id, facebook.id).status == AccountStatus.AWAITING_DECISION
    assert [a.type for a in ledger.list_actions(estate.id, facebook.id)] == []


def test_asking_twice_does_not_create_a_second_decision(world):
    ledger, estate, facebook, books = world
    act_on_account(ledger, form_model(), estate, facebook, books["social_facebook"], TODAY)

    act_on_account(ledger, form_model(), estate, facebook, books["social_facebook"], TODAY)

    assert len(ledger.open_decisions(estate.id)) == 1


def test_approved_tool_runs_on_the_next_attempt_and_is_logged(world):
    ledger, estate, facebook, books = world
    act_on_account(ledger, form_model(), estate, facebook, books["social_facebook"], TODAY)
    decision = ledger.open_decisions(estate.id)[0]
    ledger.answer_decision(estate.id, decision.id, "approve")

    report = act_on_account(ledger, form_model(), estate, facebook, books["social_facebook"], date(2026, 8, 11))

    assert report.executed == 1 and report.deferred == 0
    action = ledger.list_actions(estate.id, facebook.id)[-1]
    assert action.type == "form" and action.result == "submitted"
    assert action.payload["url"].startswith("https://www.facebook.com")
    account = ledger.get_account(estate.id, facebook.id)
    assert account.status == AccountStatus.AWAITING_REPLY
    assert account.next_action_at.date() == date(2026, 8, 25)


def test_notes_are_allowed_without_approval(world):
    ledger, estate, facebook, books = world
    model = FakeModel(text="Noted.", tool_calls=lambda p, t: [("record_note", {"note": "Needs obituary link"})] if "record_note" in t else [])

    report = act_on_account(ledger, model, estate, facebook, books["social_facebook"], TODAY)

    assert report.deferred == 0
    assert "obituary" in ledger.get_account(estate.id, facebook.id).notes
    assert ledger.open_decisions(estate.id) == []

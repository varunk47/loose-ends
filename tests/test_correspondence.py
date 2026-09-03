"""Correspondence drafts a vendor-specific notice and sends it with the certificate attached,
then records everything in the ledger."""

from datetime import date

import pytest

from loose_ends.correspondence import Notice, draft_notice, send_notice
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.models.fake import FakeModel
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate


@pytest.fixture
def world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(
        deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
        executor_email="priya@example.com", state="IL", certificate_key="certs/raymond.pdf"))
    account = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Netflix", domain="netflix.com", category="subscription", evidence=["m1"]),
        load_playbooks()))
    return ledger, estate, account, OutboxMailer(tmp_path / "mail")


def test_draft_notice_gives_the_model_the_playbook_notes_and_the_facts(world):
    ledger, estate, account, _ = world
    model = FakeModel(structured=Notice(subject="Notice of death: Raymond Okafor",
                                        body="Please cancel and refund unused time."))

    notice = draft_notice(model, estate, account, load_playbooks()["subscription"])

    assert notice.subject.startswith("Notice of death")
    assert "prorated refund" in model.last_user_text
    assert "Raymond Okafor" in model.last_user_text
    assert "Priya Okafor" in model.last_user_text


def test_send_notice_attaches_certificate_tags_subject_and_updates_ledger(world):
    ledger, estate, account, mailer = world
    notice = Notice(subject="Notice of death: Raymond Okafor", body="Please cancel.")

    updated = send_notice(ledger, mailer, estate, account, load_playbooks()["subscription"], notice,
                          today=date(2026, 8, 10))

    sent = mailer.sent()[0]
    assert sent.to == "support@netflix.com"
    assert sent.subject.endswith(f"[LE-{account.id}]")
    assert sent.attachments == ["certs/raymond.pdf"]
    assert updated.status == AccountStatus.AWAITING_REPLY
    assert updated.next_action_at.date() == date(2026, 8, 17)
    actions = ledger.list_actions(estate.id, account_id=account.id)
    assert actions[0].type == "email" and actions[0].result == "sent"
    assert actions[0].artifacts == [f"mail:{sent.id}"]


def test_send_notice_prefers_a_known_contact_address(world):
    ledger, estate, account, mailer = world
    account = ledger.update_account(estate.id, account.model_copy(update={"contact_email": "bereavement@netflix.com"}))

    send_notice(ledger, mailer, estate, account, load_playbooks()["subscription"],
                Notice(subject="Notice", body="x"), today=date(2026, 8, 10))

    assert mailer.sent()[0].to == "bereavement@netflix.com"

"""Ghost Watch: after the notices go out, watch new mail for anyone still billing a closed
account, anyone opening accounts in the deceased's name, and credit inquiries."""

from datetime import date

from loose_ends.brain import Brain
from loose_ends.discovery import Message
from loose_ends.ghostwatch import watch
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate

DOD = date(2026, 8, 3)


def make_world(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="Raymond Okafor", date_of_death=DOD, executor_name="Priya Okafor",
                                         executor_email="priya@example.com", state="IL"))
    gym = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Life Time Fitness", domain="lifetime.life", category="membership", monthly_amount=89.0),
        load_playbooks()))
    ledger.set_status(estate.id, gym.id, AccountStatus.DONE)
    return ledger, estate, gym, OutboxMailer(tmp_path / "mail")


def msg(id, sender, day, subject, body=""):
    return Message(id=id, sender=sender, sender_name=sender.split("@")[1], date=day, subject=subject, body=body)


def test_charge_after_closure_is_a_zombie_charge_with_a_drafted_dispute(tmp_path):
    ledger, estate, gym, mailer = make_world(tmp_path)
    charge = msg("pd1", "membership@lifetime.life", date(2026, 8, 20), "Your Life Time membership dues",
                 "Dues of $89.00 were charged on 2026-08-20.")

    report = watch(ledger, estate.id, [charge], Brain.offline(), today=date(2026, 8, 21))

    assert report.zombie_charges == 1
    hit = ledger.list_watches(estate.id)[0]
    assert hit.signal == "zombie_charge" and hit.account_id == gym.id and hit.evidence == ["pd1"]
    assert "89.00" in hit.draft and "closed" in hit.draft.lower()
    decision = ledger.open_decisions(estate.id)[0]
    assert decision.resumes_action == "send_dispute" and decision.options == ["send", "ignore"]


def test_welcome_mail_after_death_flags_a_new_account_and_credit_inquiries_are_flagged(tmp_path):
    ledger, estate, _, mailer = make_world(tmp_path)
    welcome = msg("pd2", "welcome@verizon.com", date(2026, 8, 22), "Welcome to Verizon! Your new line is active",
                  "Your new line ending 8830 is active.")
    inquiry = msg("pd3", "alerts@experian.com", date(2026, 8, 23), "New hard inquiry on your credit report",
                  "A hard inquiry from Synchrony Bank was added on 2026-08-22.")

    report = watch(ledger, estate.id, [welcome, inquiry], Brain.offline(), today=date(2026, 8, 24))

    signals = sorted(w.signal for w in ledger.list_watches(estate.id))
    assert signals == ["credit_inquiry", "new_account"]
    assert report.new_accounts == 1 and report.credit_inquiries == 1
    watching = [a for a in ledger.list_accounts(estate.id) if a.status == AccountStatus.WATCHING]
    assert "verizon.com" in [a.domain for a in watching]


def test_mail_before_death_and_ordinary_mail_are_ignored_and_never_rechecked(tmp_path):
    ledger, estate, _, mailer = make_world(tmp_path)
    old = msg("m1", "membership@lifetime.life", date(2026, 7, 20), "Your Life Time membership dues", "Dues of $89.00")
    ordinary = msg("pd4", "office@stjohnsnaperville.org", date(2026, 8, 20), "Weekly bulletin", "Readings.")

    first = watch(ledger, estate.id, [old, ordinary], Brain.offline(), today=date(2026, 8, 21))
    second = watch(ledger, estate.id, [old, ordinary], Brain.offline(), today=date(2026, 8, 22))

    assert first.checked == 1 and second.checked == 0
    assert ledger.list_watches(estate.id) == []

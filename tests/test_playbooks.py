"""Playbooks encode real-world procedure per account category. The planner maps an
account to one playbook deterministically; the model only adds nuance later."""

from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus


def test_bundled_playbooks_cover_the_core_categories():
    playbooks = load_playbooks()

    for category in ["credit_bureau", "subscription", "utility", "bank", "social_facebook",
                     "medical", "membership", "employer", "marketing_ddnc", "google", "generic"]:
        assert category in playbooks, category
    assert playbooks["subscription"].follow_up_days > 0
    assert "certificate" in playbooks["credit_bureau"].required_packet


def test_subscription_is_planned_as_a_reversible_email_cancellation():
    account = Account(vendor="Netflix", domain="netflix.com", category="subscription")

    planned = plan_account(account, load_playbooks())

    assert planned.playbook == "subscription"
    assert planned.status == AccountStatus.PLANNED
    assert load_playbooks()["subscription"].action == "cancel"
    assert load_playbooks()["subscription"].irreversible is False


def test_utility_always_becomes_an_executor_decision():
    account = Account(vendor="ComEd", domain="comed.com", category="utility")

    planned = plan_account(account, load_playbooks())

    assert load_playbooks()[planned.playbook].action == "decision"


def test_unknown_category_falls_back_to_generic_notify():
    account = Account(vendor="Mystery Co", domain="mystery.example", category="something_new")

    planned = plan_account(account, load_playbooks())

    assert planned.playbook == "generic"


def test_identity_protection_outranks_money_leaks_which_outrank_digital_legacy():
    playbooks = load_playbooks()
    bureau = plan_account(Account(vendor="Experian", domain="experian.com", category="credit_bureau"), playbooks)
    sub = plan_account(Account(vendor="Netflix", domain="netflix.com", category="subscription"), playbooks)
    fb = plan_account(Account(vendor="Facebook", domain="facebook.com", category="social_facebook"), playbooks)

    assert bureau.priority < sub.priority < fb.priority

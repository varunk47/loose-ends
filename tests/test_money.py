"""Money Recovered: what the agent stopped, asked back, and the hours it saved."""

from datetime import date

from loose_ends.ledger import JsonLedger
from loose_ends.money import money_recovered
from loose_ends.playbooks import load_playbooks, plan_account
from loose_ends.schema import Account, AccountStatus, Estate


def test_counter_sums_stopped_billing_refund_requests_and_hours(tmp_path):
    ledger = JsonLedger(tmp_path / "ledger")
    estate = ledger.create_estate(Estate(deceased="R", date_of_death=date(2026, 8, 3), executor_name="P",
                                         executor_email="p@example.com", state="IL"))
    books = load_playbooks()
    netflix = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Netflix", domain="netflix.com", category="subscription", monthly_amount=15.49), books))
    gym = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Gym", domain="gym.com", category="membership", monthly_amount=89.0), books))
    bureau = ledger.upsert_account(estate.id, plan_account(
        Account(vendor="Experian", domain="experian.com", category="credit_bureau"), books))
    ledger.set_status(estate.id, netflix.id, AccountStatus.DONE)
    ledger.set_status(estate.id, gym.id, AccountStatus.AWAITING_REPLY)
    ledger.set_status(estate.id, bureau.id, AccountStatus.AWAITING_REPLY)
    ledger.log_action(estate.id, netflix.id, type="reply", payload={"summary": "closed, refund 7.75"},
                      result="reply:closed")

    money = money_recovered(ledger, estate.id, books)

    assert money.monthly_stopped == 15.49
    assert money.monthly_pending == 89.0
    assert money.refunds_requested == 2
    assert money.hours_saved == books["subscription"].time_weight_hours + books["membership"].time_weight_hours \
        + books["credit_bureau"].time_weight_hours

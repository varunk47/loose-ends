"""Money Recovered: recurring billing stopped, refunds asked for, and hours the executor
did not have to spend. Computed from the ledger; nothing is stored twice."""

from __future__ import annotations

from pydantic import BaseModel

from loose_ends.ledger import JsonLedger
from loose_ends.playbooks import Playbook
from loose_ends.schema import AccountStatus

_NOT_STARTED = {AccountStatus.DISCOVERED, AccountStatus.PLANNED}
_INACTIVE = {AccountStatus.DONE, AccountStatus.PARKED, AccountStatus.FAILED, AccountStatus.WATCHING}


class MoneyRecovered(BaseModel):
    monthly_stopped: float = 0.0
    monthly_pending: float = 0.0
    refunds_requested: int = 0
    hours_saved: float = 0.0


def money_recovered(ledger: JsonLedger, estate_id: str, playbooks: dict[str, Playbook]) -> MoneyRecovered:
    money = MoneyRecovered()
    for account in ledger.list_accounts(estate_id):
        book = playbooks.get(account.playbook or "")
        if account.status == AccountStatus.DONE:
            money.monthly_stopped += account.monthly_amount or 0.0
        elif account.status not in _INACTIVE | _NOT_STARTED:
            money.monthly_pending += account.monthly_amount or 0.0
        if account.status in _NOT_STARTED or account.status == AccountStatus.WATCHING or book is None:
            continue
        money.hours_saved += book.time_weight_hours
        money.refunds_requested += book.action == "cancel"
    money.monthly_stopped = round(money.monthly_stopped, 2)
    money.monthly_pending = round(money.monthly_pending, 2)
    return money

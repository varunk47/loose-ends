"""File-backed ledger: one JSON document per estate.

The interface is deliberately small so a DynamoDB implementation can replace it without
touching the agents. Every method reads the document, builds a new one, and writes it back.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loose_ends.schema import Account, AccountStatus, Action, Cycle, Decision, Estate, now

_EMPTY: dict[str, Any] = {"estate": None, "accounts": [], "decisions": [], "actions": [], "cycles": []}


class JsonLedger:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- estates -------------------------------------------------------------------------

    def create_estate(self, estate: Estate) -> Estate:
        self._write(estate.id, {**_EMPTY, "estate": estate.model_dump(mode="json")})
        return estate.model_copy()

    def get_estate(self, estate_id: str) -> Estate:
        return Estate.model_validate(self._read(estate_id)["estate"])

    def list_estates(self) -> list[Estate]:
        return [self.get_estate(p.stem) for p in sorted(self.root.glob("*.json"))]

    def update_estate(self, estate: Estate) -> Estate:
        doc = self._read(estate.id)
        self._write(estate.id, {**doc, "estate": estate.model_dump(mode="json")})
        return estate.model_copy()

    # ---- accounts ------------------------------------------------------------------------

    def upsert_account(self, estate_id: str, account: Account) -> Account:
        doc = self._read(estate_id)
        accounts = [Account.model_validate(a) for a in doc["accounts"]]
        key = account.domain.lower()
        existing = next((a for a in accounts if a.domain.lower() == key), None)
        if existing is None:
            merged = account.model_copy()
            accounts.append(merged)
        else:
            merged = existing.model_copy(update={
                "evidence": _union(existing.evidence, account.evidence),
                "confidence": max(existing.confidence, account.confidence),
                "vendor": account.vendor or existing.vendor,
                "category": account.category or existing.category,
                "monthly_amount": account.monthly_amount or existing.monthly_amount,
            })
            accounts = [merged if a.id == existing.id else a for a in accounts]
        self._write(estate_id, {**doc, "accounts": [a.model_dump(mode="json") for a in accounts]})
        return merged

    def list_accounts(self, estate_id: str, status: AccountStatus | None = None) -> list[Account]:
        accounts = [Account.model_validate(a) for a in self._read(estate_id)["accounts"]]
        if status is not None:
            accounts = [a for a in accounts if a.status == status]
        return accounts

    def get_account(self, estate_id: str, account_id: str) -> Account:
        return next(a for a in self.list_accounts(estate_id) if a.id == account_id)

    def update_account(self, estate_id: str, account: Account) -> Account:
        doc = self._read(estate_id)
        accounts = [account if a["id"] == account.id else Account.model_validate(a) for a in doc["accounts"]]
        self._write(estate_id, {**doc, "accounts": [a.model_dump(mode="json") for a in accounts]})
        return account.model_copy()

    def set_status(self, estate_id: str, account_id: str, status: AccountStatus) -> Account:
        account = self.get_account(estate_id, account_id)
        return self.update_account(estate_id, account.model_copy(update={"status": status}))

    # ---- decisions -----------------------------------------------------------------------

    def add_decision(self, estate_id: str, decision: Decision) -> Decision:
        doc = self._read(estate_id)
        self._write(estate_id, {**doc, "decisions": [*doc["decisions"], decision.model_dump(mode="json")]})
        return decision.model_copy()

    def answer_decision(self, estate_id: str, decision_id: str, answer: str) -> Decision:
        doc = self._read(estate_id)
        decisions = [Decision.model_validate(d) for d in doc["decisions"]]
        answered = next(d for d in decisions if d.id == decision_id).model_copy(
            update={"answer": answer, "answered_at": now()}
        )
        decisions = [answered if d.id == decision_id else d for d in decisions]
        self._write(estate_id, {**doc, "decisions": [d.model_dump(mode="json") for d in decisions]})
        return answered

    def open_decisions(self, estate_id: str) -> list[Decision]:
        return [d for d in self._decisions(estate_id) if d.answer is None]

    def answered_decisions(self, estate_id: str) -> list[Decision]:
        return [d for d in self._decisions(estate_id) if d.answer is not None]

    def _decisions(self, estate_id: str) -> list[Decision]:
        return [Decision.model_validate(d) for d in self._read(estate_id)["decisions"]]

    # ---- actions and cycles --------------------------------------------------------------

    def log_action(
        self,
        estate_id: str,
        account_id: str,
        *,
        type: str,
        payload: dict[str, Any] | None = None,
        result: str = "",
        artifacts: list[str] | None = None,
    ) -> Action:
        action = Action(account_id=account_id, type=type, payload=payload or {}, result=result,
                        artifacts=artifacts or [])
        doc = self._read(estate_id)
        self._write(estate_id, {**doc, "actions": [*doc["actions"], action.model_dump(mode="json")]})
        return action

    def list_actions(self, estate_id: str, account_id: str | None = None) -> list[Action]:
        actions = [Action.model_validate(a) for a in self._read(estate_id)["actions"]]
        if account_id is not None:
            actions = [a for a in actions if a.account_id == account_id]
        return actions

    def record_cycle(self, estate_id: str, cycle: Cycle) -> Cycle:
        doc = self._read(estate_id)
        self._write(estate_id, {**doc, "cycles": [*doc["cycles"], cycle.model_dump(mode="json")]})
        return cycle

    def list_cycles(self, estate_id: str) -> list[Cycle]:
        return [Cycle.model_validate(c) for c in self._read(estate_id)["cycles"]]

    # ---- storage -------------------------------------------------------------------------

    def _path(self, estate_id: str) -> Path:
        return self.root / f"{estate_id}.json"

    def _read(self, estate_id: str) -> dict[str, Any]:
        path = self._path(estate_id)
        if not path.exists():
            raise KeyError(f"unknown estate {estate_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, estate_id: str, doc: dict[str, Any]) -> None:
        tmp = self._path(estate_id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        tmp.replace(self._path(estate_id))


def _union(first: list[str], second: list[str]) -> list[str]:
    seen: set[str] = set()
    return [x for x in [*first, *second] if not (x in seen or seen.add(x))]

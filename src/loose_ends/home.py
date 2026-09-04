"""Where local state lives: the ledger folder, the mail folders, and the config file.

`LOOSE_ENDS_HOME` overrides the default `data/local` under the repo. Read at call time so
tests and the runtime can point at a fresh folder.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import date
from pathlib import Path

from loose_ends.discovery import Message, load_mailbox
from loose_ends.ledger import JsonLedger
from loose_ends.mail import OutboxMailer
from loose_ends.schema import Estate

REPO = Path(__file__).resolve().parents[2]
DEMO_INBOX = REPO / "data" / "synthetic" / "raymond_okafor.json"
DEMO_POST_DEATH = REPO / "data" / "synthetic" / "post_death.json"


def load_inbox(home: Path, today: date) -> list[Message]:
    """The main inbox plus any post-death mail that has "arrived" by today."""
    config = config_for(home)
    messages = load_mailbox(config["inbox"])
    if config.get("post_death"):
        messages += [m for m in load_mailbox(config["post_death"]) if m.date <= today]
    return messages


def home_dir() -> Path:
    return Path(os.environ.get("LOOSE_ENDS_HOME", REPO / "data" / "local"))


def ledger_for(home: Path) -> JsonLedger:
    return JsonLedger(home / "ledger")


def mailer_for(home: Path) -> OutboxMailer:
    return OutboxMailer(home / "mail")


def config_for(home: Path) -> dict:
    path = home / "config.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_config(home: Path, config: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(json.dumps(config), encoding="utf-8")


def seed_demo(home: Path, inbox: Path | None = None) -> Estate:
    home.mkdir(parents=True, exist_ok=True)
    estate = ledger_for(home).create_estate(Estate(
        deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
        executor_email="priya.okafor@example.com", executor_relationship="daughter and executor",
        state="IL", certificate_key="certificates/raymond_okafor_certificate.pdf"))
    write_config(home, {"inbox": str(inbox or DEMO_INBOX), "post_death": str(DEMO_POST_DEATH) if inbox is None else ""})
    return estate


def reset_home(home: Path) -> None:
    for child in home.iterdir() if home.exists() else []:
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def current_estate(home: Path, estate_id: str | None = None) -> Estate:
    ledger = ledger_for(home)
    if estate_id:
        return ledger.get_estate(estate_id)
    estates = ledger.list_estates()
    if not estates:
        raise LookupError("no estate yet; run `loose-ends init --demo` first")
    return estates[0]

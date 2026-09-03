"""Command line for running Loose Ends locally. Every command prints JSON.

  loose-ends init --demo                 create the Raymond Okafor demo estate
  loose-ends cycle --brain offline       run one background cycle
  loose-ends status                      accounts, decisions, cycles
  loose-ends answer <decision> <choice>  answer a decision; the next cycle resumes
  loose-ends reply <account> --body ...  simulate a vendor reply
  loose-ends reset --yes                 wipe the home folder
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from loose_ends.brain import Brain
from loose_ends.discovery import load_json_mailbox
from loose_ends.graph import run_cycle_graph
from loose_ends.home import (
    DEMO_INBOX,
    config_for,
    current_estate,
    home_dir,
    ledger_for,
    mailer_for,
    write_config,
)
from loose_ends.mail import IncomingMail, tracking_token
from loose_ends.models import get_model
from loose_ends.playbooks import load_playbooks
from loose_ends.schema import Estate, new_id

app = typer.Typer(add_completion=False, help=__doc__)


@app.callback()
def main(ctx: typer.Context,
         home: Annotated[Path | None, typer.Option(help="Where the ledger and mail live.")] = None) -> None:
    ctx.obj = home or home_dir()


def _out(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))


def _estate(home: Path) -> Estate:
    try:
        return current_estate(home)
    except LookupError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command()
def init(ctx: typer.Context, demo: bool = typer.Option(False, help="Seed the Raymond Okafor demo estate."),
         inbox: Path | None = typer.Option(None, help="Path to a JSON mailbox.")) -> None:
    """Create an estate. With --demo, seed Raymond Okafor and point at the synthetic inbox."""
    home: Path = ctx.obj
    if not demo:
        raise typer.BadParameter("only --demo is supported from the CLI for now; use the dashboard for real intake")
    home.mkdir(parents=True, exist_ok=True)
    estate = ledger_for(home).create_estate(Estate(
        deceased="Raymond Okafor", date_of_death=date(2026, 8, 3), executor_name="Priya Okafor",
        executor_email="priya.okafor@example.com", executor_relationship="daughter and executor",
        state="IL", certificate_key="certificates/raymond_okafor_certificate.pdf"))
    write_config(home, {"inbox": str(inbox or DEMO_INBOX)})
    _out({"estate_id": estate.id, "deceased": estate.deceased, "inbox": str(inbox or DEMO_INBOX)})


@app.command()
def cycle(ctx: typer.Context,
          brain: str = typer.Option("offline", help="offline | bedrock | fake"),
          today: str | None = typer.Option(None, help="ISO date; defaults to today.")) -> None:
    """Run one background cycle: discover, plan, dispatch, follow up, digest."""
    home: Path = ctx.obj
    estate = _estate(home)
    messages = load_json_mailbox(config_for(home)["inbox"])
    the_brain = Brain.offline() if brain == "offline" else Brain.from_model(get_model(brain))
    report, _ = run_cycle_graph(ledger_for(home), estate.id, messages, the_brain, mailer_for(home), load_playbooks(),
                                today=date.fromisoformat(today) if today else date.today())
    _out(report.model_dump())


@app.command()
def status(ctx: typer.Context) -> None:
    """Accounts, open decisions, and cycle history."""
    home: Path = ctx.obj
    ledger = ledger_for(home)
    estate = _estate(home)
    accounts = ledger.list_accounts(estate.id)
    counts: dict[str, int] = {}
    for account in accounts:
        counts[account.status.value] = counts.get(account.status.value, 0) + 1
    _out({
        "estate_id": estate.id,
        "deceased": estate.deceased,
        "counts": counts,
        "open_decisions": [d.model_dump() for d in ledger.open_decisions(estate.id)],
        "accounts": [a.model_dump() for a in sorted(accounts, key=lambda a: (a.priority, a.vendor))],
        "cycles": [c.model_dump() for c in ledger.list_cycles(estate.id)],
        "sent_mail": len(mailer_for(home).sent()),
    })


@app.command()
def answer(ctx: typer.Context, decision_id: str, choice: str) -> None:
    """Answer an open decision. The next cycle resumes the account."""
    home: Path = ctx.obj
    estate = _estate(home)
    _out(ledger_for(home).answer_decision(estate.id, decision_id, choice).model_dump())


@app.command()
def reply(ctx: typer.Context, account_id: str,
          body: str = typer.Option(..., help="Reply text."),
          sender: str | None = typer.Option(None, help="Defaults to support@<vendor domain>.")) -> None:
    """Simulate a vendor reply so the follow-up loop has something to read."""
    home: Path = ctx.obj
    estate = _estate(home)
    account = ledger_for(home).get_account(estate.id, account_id)
    mail = IncomingMail(id=new_id(), sender=sender or f"support@{account.domain}", date=date.today(),
                        subject=f"Re: Notice of death {tracking_token(account.id)}", body=body)
    mailer_for(home).drop_reply(mail)
    _out(mail.model_dump())


@app.command()
def reset(ctx: typer.Context, yes: bool = typer.Option(False, "--yes", help="Confirm.")) -> None:
    """Wipe the home folder: ledger, mail, config."""
    home: Path = ctx.obj
    if not yes:
        raise typer.BadParameter("pass --yes to confirm")
    for child in home.iterdir() if home.exists() else []:
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    _out({"reset": str(home)})

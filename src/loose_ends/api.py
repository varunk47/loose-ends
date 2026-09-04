"""HTTP API for the dashboard. Wraps the same handlers as the AgentCore runtime entrypoint.

Run locally: uv run uvicorn loose_ends.api:app --reload --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from loose_ends.home import home_dir, ledger_for, mailer_for, reset_home, seed_demo
from loose_ends.mail import IncomingMail, tracking_token
from loose_ends.runtime import handle
from loose_ends.schema import new_id

app = FastAPI(title="Loose Ends")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])


class CycleRequest(BaseModel):
    brain: str = "offline"
    today: str | None = None


class AnswerRequest(BaseModel):
    choice: str


class ReplyRequest(BaseModel):
    account_id: str
    body: str
    sender: str | None = None


def _ok(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("ok"):
        return response
    error = response.get("error", "")
    raise HTTPException(status_code=404 if "no estate yet" in error else 400, detail=error)


@app.post("/api/init-demo")
def init_demo() -> dict[str, Any]:
    estate = seed_demo(home_dir())
    return {"ok": True, "estate_id": estate.id}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return _ok(handle({"action": "status"}))


@app.post("/api/cycle")
def cycle(request: CycleRequest) -> dict[str, Any]:
    return _ok(handle({"action": "run_cycle", "brain": request.brain, "today": request.today}))


@app.post("/api/decisions/{decision_id}/answer")
def answer(decision_id: str, request: AnswerRequest) -> dict[str, Any]:
    return _ok(handle({"action": "answer", "decision_id": decision_id, "choice": request.choice}))


class PauseRequest(BaseModel):
    until: str | None = None


@app.post("/api/pause")
def pause(request: PauseRequest) -> dict[str, Any]:
    return _ok(handle({"action": "pause", "until": request.until}))


@app.get("/api/mail")
def mail() -> dict[str, Any]:
    mailer = mailer_for(home_dir())
    return {"ok": True, "sent": [m.model_dump(mode="json") for m in reversed(mailer.sent())]}


@app.post("/api/reply")
def reply(request: ReplyRequest) -> dict[str, Any]:
    home = home_dir()
    status = _ok(handle({"action": "status"}))
    account = ledger_for(home).get_account(status["estate_id"], request.account_id)
    incoming = IncomingMail(id=new_id(), sender=request.sender or f"support@{account.domain}",
                            date=__import__("datetime").date.today(),
                            subject=f"Re: Notice of death {tracking_token(account.id)}", body=request.body)
    mailer_for(home).drop_reply(incoming)
    return {"ok": True, "reply": incoming.model_dump(mode="json")}


@app.post("/api/reset")
def reset() -> dict[str, Any]:
    reset_home(home_dir())
    return {"ok": True}

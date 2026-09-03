"""The AgentCore Runtime entrypoint: one payload in, one cycle report out. EventBridge will
call it on a schedule; the dashboard calls it on demand."""

import json

from typer.testing import CliRunner

from loose_ends.cli import app as cli
from loose_ends.runtime import handle


def seeded_home(tmp_path):
    result = CliRunner().invoke(cli, ["--home", str(tmp_path), "init", "--demo"], catch_exceptions=False)
    return json.loads(result.output)["estate_id"]


def test_run_cycle_payload_returns_the_report(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_HOME", str(tmp_path))
    estate_id = seeded_home(tmp_path)

    response = handle({"action": "run_cycle", "estate_id": estate_id, "brain": "offline", "today": "2026-08-10"})

    assert response["ok"] is True
    assert response["report"]["discovered"] >= 25
    assert response["estate_id"] == estate_id


def test_status_payload_returns_counts_and_decisions(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_HOME", str(tmp_path))
    estate_id = seeded_home(tmp_path)
    handle({"action": "run_cycle", "estate_id": estate_id, "brain": "offline", "today": "2026-08-10"})

    response = handle({"action": "status", "estate_id": estate_id})

    assert response["ok"] is True
    assert response["counts"]["awaiting_decision"] >= 3
    assert len(response["open_decisions"]) >= 3


def test_unknown_action_is_a_clean_error(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_HOME", str(tmp_path))

    response = handle({"action": "explode"})

    assert response["ok"] is False and "explode" in response["error"]

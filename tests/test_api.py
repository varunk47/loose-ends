"""The HTTP API the dashboard talks to. Locally it wraps the same handlers as the AgentCore
runtime entrypoint; in production the dashboard calls the runtime through this shape."""

import pytest
from fastapi.testclient import TestClient

from loose_ends.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_HOME", str(tmp_path))
    return TestClient(app)


def test_init_demo_then_status(client):
    created = client.post("/api/init-demo").json()

    status = client.get("/api/status").json()

    assert status["estate_id"] == created["estate_id"]
    assert status["estate"]["deceased"] == "Raymond Okafor"
    assert status["counts"] == {}


def test_cycle_then_decisions_then_answer_then_mail(client):
    client.post("/api/init-demo")

    report = client.post("/api/cycle", json={"brain": "offline", "today": "2026-08-10"}).json()
    assert report["ok"] and report["report"]["decisions"] >= 3

    status = client.get("/api/status").json()
    decision = status["open_decisions"][0]
    answered = client.post(f"/api/decisions/{decision['id']}/answer", json={"choice": decision["options"][0]}).json()
    assert answered["decision"]["answer"] == decision["options"][0]

    mail = client.get("/api/mail").json()
    assert len(mail["sent"]) >= 20
    assert any(m["to"].startswith("priya") for m in mail["sent"])


def test_reset_clears_everything(client):
    client.post("/api/init-demo")
    client.post("/api/cycle", json={"brain": "offline", "today": "2026-08-10"})

    client.post("/api/reset")

    assert client.get("/api/status").status_code == 404

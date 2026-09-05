"""Real intake: an executor creates an estate from their own details and an exported inbox,
through the API or the CLI, without the demo seed."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from loose_ends.api import app
from loose_ends.cli import app as cli

MBOX = Path(__file__).parent / "fixtures" / "inbox_small.mbox"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_HOME", str(tmp_path))
    return TestClient(app)


def test_api_creates_an_estate_from_executor_details_and_an_uploaded_mbox(client, tmp_path):
    with MBOX.open("rb") as f:
        created = client.post("/api/estates", data={
            "deceased": "Grace Okafor", "date_of_death": "2026-08-20", "executor_name": "Daniel Okafor",
            "executor_email": "daniel@example.com", "executor_relationship": "son and executor", "state": "IL",
            "packet": "certificate,executor_id",
        }, files={"inbox": ("export.mbox", f, "application/mbox")}).json()

    assert created["ok"] and created["estate_id"]
    status = client.get("/api/status").json()
    assert status["estate"]["deceased"] == "Grace Okafor"
    assert status["estate"]["packet"] == ["certificate", "executor_id"]
    report = client.post("/api/cycle", json={"brain": "offline", "today": "2026-08-25"}).json()
    assert report["report"]["discovered"] >= 2


def test_cli_init_with_real_details(tmp_path):
    inbox = tmp_path / "export.mbox"
    shutil.copy(MBOX, inbox)

    result = CliRunner().invoke(cli, ["--home", str(tmp_path / "home"), "init", "--deceased", "Grace Okafor",
                                      "--date-of-death", "2026-08-20", "--executor", "Daniel Okafor",
                                      "--email", "daniel@example.com", "--state", "IL", "--inbox", str(inbox)],
                                catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["deceased"] == "Grace Okafor"

"""The CLI is how a teammate runs the demo without the dashboard: create the estate, run a
cycle, see what needs the executor, answer, run again."""

import json

from typer.testing import CliRunner

from loose_ends.cli import app

runner = CliRunner()


def run(home, *args):
    result = runner.invoke(app, ["--home", str(home), *args], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


def test_demo_flow_init_cycle_answer_cycle(tmp_path):
    out = run(tmp_path, "init", "--demo")
    estate_id = json.loads(out)["estate_id"]

    first = json.loads(run(tmp_path, "cycle", "--brain", "offline", "--today", "2026-08-10"))
    assert first["discovered"] >= 25 and first["decisions"] >= 3

    status = json.loads(run(tmp_path, "status"))
    assert status["estate_id"] == estate_id
    assert status["counts"]["awaiting_decision"] >= 3
    decision = status["open_decisions"][0]

    run(tmp_path, "answer", decision["id"], decision["options"][0])
    second = json.loads(run(tmp_path, "cycle", "--brain", "offline", "--today", "2026-08-11"))
    assert second["resumed"] == 1


def test_reply_command_feeds_the_follow_up_loop(tmp_path):
    run(tmp_path, "init", "--demo")
    run(tmp_path, "cycle", "--brain", "offline", "--today", "2026-08-10")
    status = json.loads(run(tmp_path, "status"))
    account = next(a for a in status["accounts"] if a["status"] == "awaiting_reply")

    run(tmp_path, "reply", account["id"], "--body", "We have closed the account and issued a refund.")
    report = json.loads(run(tmp_path, "cycle", "--brain", "offline", "--today", "2026-08-11"))

    assert report["closed"] == 1


def test_reset_wipes_the_home_folder(tmp_path):
    run(tmp_path, "init", "--demo")
    run(tmp_path, "reset", "--yes")

    assert not any(tmp_path.iterdir())

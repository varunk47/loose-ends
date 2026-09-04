"""Google Takeout delivers a .mbox. It must load into the same Message shape as the JSON
mailbox so discovery does not care where mail came from."""

from datetime import date
from pathlib import Path

from loose_ends.discovery import load_mailbox, load_mbox

FIXTURE = Path(__file__).parent / "fixtures" / "inbox_small.mbox"


def test_mbox_messages_have_ids_senders_dates_and_plain_text_bodies():
    messages = load_mbox(FIXTURE)

    assert [m.date for m in messages] == [date(2026, 7, 2), date(2026, 7, 10), date(2026, 7, 14)]
    netflix, comed, ada = messages
    assert netflix.id == "billing-2026-07@mailer.netflix.com"
    assert netflix.sender == "info@mailer.netflix.com" and netflix.sender_name == "Netflix"
    assert netflix.sender_domain == "netflix.com"
    assert comed.subject == "Your ComEd statement is ready"
    assert "$142.17" in comed.body and "<html>" not in comed.body
    assert ada.id, "messages without a Message-ID still get a stable id"
    assert "Grandpa" in ada.body and "<p>" not in ada.body


def test_load_mailbox_picks_the_format_from_the_extension():
    assert len(load_mailbox(FIXTURE)) == 3
    assert len(load_mailbox(FIXTURE.with_suffix(".json"))) == 6

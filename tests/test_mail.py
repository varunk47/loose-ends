"""The outbox mailer is the local stand-in for SES: sent mail lands in a folder, and replies
can be dropped into a folder for the follow-up loop to read."""

from datetime import date

from loose_ends.mail import IncomingMail, OutboxMailer, extract_token, tracking_token


def test_send_records_the_message_and_returns_it(tmp_path):
    mailer = OutboxMailer(tmp_path)

    sent = mailer.send(to="support@netflix.com", subject="Notice", body="Hello", attachments=["cert.pdf"])

    assert sent.to == "support@netflix.com"
    assert sent.attachments == ["cert.pdf"]
    assert [m.id for m in mailer.sent()] == [sent.id]
    assert OutboxMailer(tmp_path).sent()[0].subject == "Notice"


def test_tracking_token_round_trips_through_a_reply_subject():
    token = tracking_token("abc123")

    assert extract_token(f"Re: Notice of death {token}") == "abc123"
    assert extract_token("Re: something else") is None


def test_replies_dropped_in_the_inbox_folder_are_read_once(tmp_path):
    mailer = OutboxMailer(tmp_path)
    mailer.drop_reply(IncomingMail(id="r1", sender="support@netflix.com", date=date(2026, 8, 12),
                                   subject="Re: Notice [LE-abc123]", body="Account closed."))

    first = mailer.read_replies()
    second = mailer.read_replies()

    assert [r.id for r in first] == ["r1"]
    assert first[0].token == "abc123"
    assert second == []

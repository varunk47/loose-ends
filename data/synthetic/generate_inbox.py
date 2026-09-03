"""Generate the Raymond Okafor demo inbox from vendors.yaml.

Run: uv run python data/synthetic/generate_inbox.py
Writes data/synthetic/raymond_okafor.json (24 months of mail ending Aug 2026) and
data/synthetic/post_death.json (mail that arrives after the notifications go out, for Ghost Watch).
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import yaml

HERE = Path(__file__).parent
START = date(2024, 9, 1)
END = date(2026, 8, 3)  # date of death
SEED = 20260803

CADENCE_DAYS = {"monthly": 30, "quarterly": 91, "yearly": 365, "irregular": 45}


def main() -> None:
    rng = random.Random(SEED)
    vendors = yaml.safe_load((HERE / "vendors.yaml").read_text(encoding="utf-8"))
    messages = []
    for vendor in vendors:
        messages.extend(_series(vendor, rng))
    messages.sort(key=lambda m: m["date"])
    for i, m in enumerate(messages, 1):
        m["id"] = f"m{i:04d}"
    (HERE / "raymond_okafor.json").write_text(json.dumps(messages, indent=1), encoding="utf-8")
    (HERE / "post_death.json").write_text(json.dumps(_post_death(), indent=1), encoding="utf-8")
    print(f"{len(messages)} messages from {len(vendors)} senders")


def _series(vendor: dict, rng: random.Random) -> list[dict]:
    if vendor["cadence"] == "once":
        return [_message(vendor, START + timedelta(days=rng.randint(0, 60)), rng)]
    step = CADENCE_DAYS[vendor["cadence"]]
    day = START + timedelta(days=rng.randint(0, step))
    out = []
    while day <= END:
        out.append(_message(vendor, day, rng))
        day += timedelta(days=step + rng.randint(-2, 2))
    return out


def _message(vendor: dict, day: date, rng: random.Random) -> dict:
    amount = vendor.get("amount")
    body = vendor["body"].format(
        amount=f"{amount:.2f}" if amount else "",
        date=day.isoformat(),
        due=(day + timedelta(days=21)).isoformat(),
        year=day.year,
    )
    sender = rng.choice(vendor["senders"])
    return {
        "sender": sender,
        "sender_name": vendor["vendor"] if vendor["kind"] != "personal" else sender.split("@")[0].replace(".", " ").title(),
        "date": day.isoformat(),
        "subject": rng.choice(vendor["subjects"]),
        "body": body,
    }


def _post_death() -> list[dict]:
    return [
        {"id": "pd001", "sender": "membership@lifetime.life", "sender_name": "Life Time Fitness",
         "date": "2026-08-20", "subject": "Your Life Time membership dues",
         "body": "Dues of $89.00 were charged on 2026-08-20."},
        {"id": "pd002", "sender": "welcome@verizon.com", "sender_name": "Verizon",
         "date": "2026-08-22", "subject": "Welcome to Verizon! Your new line is active",
         "body": "Thanks for choosing Verizon. Your new line ending 8830 is active. Device: iPhone 16 Pro."},
        {"id": "pd003", "sender": "alerts@experian.com", "sender_name": "Experian",
         "date": "2026-08-23", "subject": "New hard inquiry on your credit report",
         "body": "A hard inquiry from Synchrony Bank was added to your report on 2026-08-22."},
        {"id": "pd004", "sender": "donate@redcross.org", "sender_name": "American Red Cross",
         "date": "2026-08-25", "subject": "Thank you for your monthly gift",
         "body": "Your monthly donation of $25.00 was received on 2026-08-25."},
    ]


if __name__ == "__main__":
    main()

"""Bank and card statement exports as a discovery channel.

Recurring debits (the same merchant in two or more months) become synthetic messages so the
rest of the pipeline, classifier and aggregation included, does not care where they came from.
Merchants the vendor directory knows get their real domain; the rest get `<slug>.statement`.
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import date
from pathlib import Path

from loose_ends.discovery import Message
from loose_ends.vendors import VendorDirectory

_NOISE = re.compile(r"[^A-Z ]+")


def load_statement_csv(path: Path | str, directory: VendorDirectory) -> list[Message]:
    rows = _read_rows(path)
    debits = [(day, desc, amt) for day, desc, amt in rows if amt < 0]
    months_by_key: dict[str, set[tuple[int, int]]] = {}
    for day, desc, _ in debits:
        months_by_key.setdefault(_key(desc), set()).add((day.year, day.month))
    recurring = {key for key, months in months_by_key.items() if len(months) >= 2}

    messages = []
    for day, desc, amt in debits:
        key = _key(desc)
        if key not in recurring:
            continue
        entry = directory.lookup_name(desc)
        if entry:
            sender, name = f"billing@{entry.domain}", entry.vendor
        else:
            sender, name = f"billing@{_slug(key)}.statement", key.title()
        digest = hashlib.sha1(f"{day.isoformat()}|{desc}|{amt}".encode()).hexdigest()[:12]
        messages.append(Message(
            id=f"stmt-{digest}", sender=sender, sender_name=name, date=day,
            subject=f"Recurring charge: {key}",
            body=f"{desc} charged ${abs(amt):.2f} on {day.isoformat()} (from the statement export)",
        ))
    return sorted(messages, key=lambda m: (m.date, m.id))


def _read_rows(path: Path | str) -> list[tuple[date, str, float]]:
    rows = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = {name.lower().strip(): name for name in reader.fieldnames or []}
        for raw in reader:
            try:
                day = date.fromisoformat(raw[fields["date"]].strip())
                amount = float(raw[fields["amount"]].replace("$", "").replace(",", "").strip())
            except (KeyError, ValueError):
                continue
            rows.append((day, raw[fields["description"]].strip(), amount))
    return rows


def _key(description: str) -> str:
    """"NETFLIX.COM 866-579-7172" -> "NETFLIX COM"; "HULU 877-485-8411 CA" -> "HULU"."""
    words = [w for w in _NOISE.sub(" ", description.upper()).split() if len(w) > 2]
    return " ".join(words[:2]) if words else description.upper()


def _slug(key: str) -> str:
    return "".join(c for c in key.lower() if c.isalnum()) or "merchant"

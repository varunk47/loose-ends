"""The three judgment calls the pipeline makes, bundled so they can be swapped as a set:
a Bedrock-backed brain for the real thing, a rule-based brain for offline runs and tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from strands.models import Model

from loose_ends.correspondence import Notice, draft_notice
from loose_ends.discovery import Classifier, build_classifier
from loose_ends.followup import ReplyOutcome, classify_reply
from loose_ends.mail import IncomingMail
from loose_ends.playbooks import Playbook
from loose_ends.schema import Account, Estate
from loose_ends.vendors import (
    VendorDirectory,
    rule_classifier,
    rule_reply_classifier,
    template_notice,
)

Drafter = Callable[[Estate, Account, Playbook, str | None], Notice]
ReplyClassifier = Callable[[IncomingMail, Account], ReplyOutcome]


@dataclass(frozen=True)
class Brain:
    classify_messages: Classifier
    draft: Drafter
    classify_reply: ReplyClassifier

    @classmethod
    def from_model(cls, model: Model) -> Brain:
        return cls(build_classifier(model), partial(draft_notice, model), partial(classify_reply, model))

    @classmethod
    def offline(cls, directory: VendorDirectory | None = None) -> Brain:
        return cls(rule_classifier(directory or VendorDirectory.load()), template_notice, rule_reply_classifier)

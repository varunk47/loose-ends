"""Model selection by name. "fake" for tests, "bedrock" for the real thing."""

from __future__ import annotations

import os

from strands.models import BedrockModel, Model

from loose_ends.models.fake import FakeModel

DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-5"
DEFAULT_REGION = "us-east-1"


def get_model(name: str) -> Model:
    match name:
        case "fake":
            return FakeModel()
        case "bedrock":
            return BedrockModel(
                model_id=os.environ.get("LOOSE_ENDS_MODEL_ID", DEFAULT_MODEL_ID),
                region_name=os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", DEFAULT_REGION)),
            )
        case _:
            raise ValueError(f"unknown model {name!r}; use 'fake' or 'bedrock'")

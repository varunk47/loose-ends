"""Model selection by name, so the same code runs on the fake model in tests and on Bedrock
in production with one flag."""

import pytest
from strands.models import BedrockModel

from loose_ends.models import get_model
from loose_ends.models.fake import FakeModel


def test_fake_by_name():
    assert isinstance(get_model("fake"), FakeModel)


def test_bedrock_defaults_to_sonnet_5_in_us_east_1(monkeypatch):
    monkeypatch.delenv("LOOSE_ENDS_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    model = get_model("bedrock")

    assert isinstance(model, BedrockModel)
    assert model.get_config()["model_id"] == "global.anthropic.claude-sonnet-5"


def test_bedrock_model_id_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LOOSE_ENDS_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    assert get_model("bedrock").get_config()["model_id"] == "us.anthropic.claude-sonnet-4-6"


def test_unknown_name_is_an_error():
    with pytest.raises(ValueError):
        get_model("gpt-9")

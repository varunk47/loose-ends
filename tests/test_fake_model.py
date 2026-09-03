"""The fake model lets every agent run offline. It answers with canned text or a canned
structured object, and records what it was asked so tests can assert on prompts."""

from pydantic import BaseModel
from strands import Agent

from loose_ends.models.fake import FakeModel


class Verdict(BaseModel):
    vendor: str
    category: str
    confidence: float


def test_fake_model_returns_canned_text():
    model = FakeModel(text="Hello, executor.")
    agent = Agent(model=model, callback_handler=None)

    result = agent("anything")

    assert str(result).strip() == "Hello, executor."
    assert "anything" in model.last_user_text


def test_fake_model_returns_canned_structured_output():
    model = FakeModel(structured=Verdict(vendor="Netflix", category="subscription", confidence=0.9))
    agent = Agent(model=model, callback_handler=None)

    result = agent("classify this email", structured_output_model=Verdict)

    assert result.structured_output == Verdict(
        vendor="Netflix", category="subscription", confidence=0.9
    )


def test_fake_model_can_answer_from_a_function_of_the_prompt():
    model = FakeModel(structured=lambda prompt: Verdict(
        vendor="ComEd" if "electric" in prompt else "Unknown",
        category="utility",
        confidence=0.8,
    ))
    agent = Agent(model=model, callback_handler=None)

    result = agent("electric bill from ComEd", structured_output_model=Verdict)

    assert result.structured_output.vendor == "ComEd"

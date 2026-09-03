"""An offline Strands model provider for tests and local development.

It answers with canned text or a canned Pydantic object. Structured output in Strands is
delivered as a forced tool call whose tool name is the Pydantic class name, so when the
event loop offers that tool we emit a toolUse block; otherwise we emit plain text.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from typing import Any

from pydantic import BaseModel
from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

TextSource = str | Callable[[str], str]
StructuredSource = BaseModel | Callable[[str], BaseModel] | None


class FakeModel(Model):
    def __init__(self, text: TextSource = "", structured: StructuredSource = None) -> None:
        self._text = text
        self._structured = structured
        self.last_user_text: str = ""
        self.calls: list[dict[str, Any]] = []

    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {"model_id": "fake"}

    async def structured_output(
        self, output_model: type[BaseModel], prompt: Messages, system_prompt: str | None = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        self.last_user_text = _last_user_text(prompt)
        yield {"output": self._resolve_structured(self.last_user_text)}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        self.last_user_text = _last_user_text(messages)
        self.calls.append({"prompt": self.last_user_text, "tools": [t["name"] for t in tool_specs or []]})

        obj = self._resolve_structured(self.last_user_text)
        offered = {t["name"] for t in tool_specs or []}
        yield {"messageStart": {"role": "assistant"}}
        if obj is not None and type(obj).__name__ in offered:
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"name": type(obj).__name__, "toolUseId": uuid.uuid4().hex}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(obj.model_dump(mode="json"))}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": self._resolve_text(self.last_user_text)}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}, "metrics": {"latencyMs": 0}}}

    def _resolve_text(self, prompt: str) -> str:
        return self._text(prompt) if callable(self._text) else self._text

    def _resolve_structured(self, prompt: str) -> BaseModel | None:
        if self._structured is None:
            return None
        return self._structured(prompt) if callable(self._structured) else self._structured


def _last_user_text(messages: Messages) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return " ".join(block.get("text", "") for block in message.get("content", []) if "text" in block)
    return ""

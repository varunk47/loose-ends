"""An offline Strands model provider for tests and local development.

It answers with canned text, a canned Pydantic object, or canned tool calls. Structured
output in Strands is delivered as a forced tool call whose tool name is the Pydantic class
name, so when the event loop offers that tool we emit a toolUse block.
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
ToolCallSource = Callable[[str, list[str]], list[tuple[str, dict[str, Any]]]] | None


class FakeModel(Model):
    def __init__(self, text: TextSource = "", structured: StructuredSource = None,
                 tool_calls: ToolCallSource = None) -> None:
        self._text = text
        self._structured = structured
        self._tool_calls = tool_calls
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
        offered = [t["name"] for t in tool_specs or []]
        self.calls.append({"prompt": self.last_user_text, "tools": offered})

        obj = self._resolve_structured(self.last_user_text)
        yield {"messageStart": {"role": "assistant"}}
        if obj is not None and type(obj).__name__ in offered:
            for event in _tool_use_events(type(obj).__name__, obj.model_dump(mode="json")):
                yield event
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        elif (calls := self._pending_tool_calls(messages, offered)):
            for name, payload in calls:
                for event in _tool_use_events(name, payload):
                    yield event
                yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": self._resolve_text(self.last_user_text)}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0}, "metrics": {"latencyMs": 0}}}

    def _pending_tool_calls(self, messages: Messages, offered: list[str]) -> list[tuple[str, dict[str, Any]]]:
        if self._tool_calls is None or _last_message_has_tool_result(messages):
            return []
        return [(name, payload) for name, payload in self._tool_calls(self.last_user_text, offered) if name in offered]

    def _resolve_text(self, prompt: str) -> str:
        return self._text(prompt) if callable(self._text) else self._text

    def _resolve_structured(self, prompt: str) -> BaseModel | None:
        if self._structured is None:
            return None
        return self._structured(prompt) if callable(self._structured) else self._structured


def _tool_use_events(name: str, payload: dict[str, Any]) -> list[StreamEvent]:
    """The block start and full input for one tool use; the caller closes the block."""
    return [
        {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": uuid.uuid4().hex}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}},
    ]


def _last_user_text(messages: Messages) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return " ".join(block.get("text", "") for block in message.get("content", []) if "text" in block)
    return ""


def _last_message_has_tool_result(messages: Messages) -> bool:
    if not messages:
        return False
    return any("toolResult" in block for block in messages[-1].get("content", []))

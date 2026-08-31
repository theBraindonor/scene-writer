import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from scene.agent.config import LLMConfig
from scene.agent.llm import stream_complete
from scene.agent.prompts import load_prompts

DEFAULT_SYSTEM_PROMPT = load_prompts().coordinator_system_prompt


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ReasoningDelta:
    text: str


@dataclass(frozen=True)
class ContentDelta:
    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    name: str


@dataclass(frozen=True)
class ToolCallFinished:
    name: str


@dataclass(frozen=True)
class TurnComplete:
    pass


TurnEvent = ReasoningDelta | ContentDelta | ToolCallStarted | ToolCallFinished | TurnComplete


def run_turn(
    config: LLMConfig,
    history: list[dict[str, Any]],
    user_message: str,
    tools: Sequence[Tool] = (),
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Iterator[TurnEvent]:
    tools_by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema for tool in tools] or None

    history.append({"role": "user", "content": user_message})

    while True:
        messages = [{"role": "system", "content": system_prompt}, *history]

        content_parts: list[str] = []
        tool_call_accumulators: dict[int, dict[str, str | None]] = {}
        announced_indexes: set[int] = set()
        tool_call_order: list[int] = []

        for chunk in stream_complete(config, messages, tools=schemas):
            delta = chunk.choices[0].delta

            reasoning_piece = getattr(delta, "reasoning_content", None)
            if reasoning_piece:
                yield ReasoningDelta(reasoning_piece)

            content_piece = getattr(delta, "content", None)
            if content_piece:
                content_parts.append(content_piece)
                yield ContentDelta(content_piece)

            for tool_call_delta in getattr(delta, "tool_calls", None) or []:
                index = tool_call_delta.index
                accumulator = tool_call_accumulators.setdefault(index, {"id": None, "name": "", "arguments": ""})
                if index not in tool_call_order:
                    tool_call_order.append(index)
                if tool_call_delta.id:
                    accumulator["id"] = tool_call_delta.id
                function = getattr(tool_call_delta, "function", None)
                if function is not None:
                    if function.name:
                        accumulator["name"] += function.name
                    if function.arguments:
                        accumulator["arguments"] += function.arguments
                if accumulator["name"] and index not in announced_indexes:
                    announced_indexes.add(index)
                    yield ToolCallStarted(accumulator["name"])

        full_content = "".join(content_parts) or None
        tool_calls = [tool_call_accumulators[index] for index in tool_call_order] or None

        assistant_message: dict[str, Any] = {"role": "assistant", "content": full_content}
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {"name": tool_call["name"], "arguments": tool_call["arguments"]},
                }
                for tool_call in tool_calls
            ]
        history.append(assistant_message)

        if not tool_calls:
            yield TurnComplete()
            return

        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call["name"])
            if tool is None:
                result: Any = {"error": f"Unknown tool: {tool_call['name']!r}"}
            else:
                arguments = json.loads(tool_call["arguments"]) if tool_call["arguments"] else {}
                result = tool.handler(arguments)
            history.append({"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result)})
            yield ToolCallFinished(tool_call["name"])

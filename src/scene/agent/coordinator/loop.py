import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from scene.agent.config import LLMConfig
from scene.agent.llm import complete

DEFAULT_SYSTEM_PROMPT = (
    "You are the Scene Writer coordinating agent. You help a writer develop a story by "
    "chatting with them and using the tools available to you to view and edit its data. "
    "Right now you can view and edit the story's title, scenario, and style guidance. "
    "Chat naturally, ask clarifying questions, and use your tools to make the changes the "
    "writer asks for rather than just describing what they should do."
)


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


def run_turn(
    config: LLMConfig,
    history: list[dict[str, Any]],
    user_message: str,
    tools: Sequence[Tool] = (),
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> str:
    tools_by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema for tool in tools] or None

    history.append({"role": "user", "content": user_message})

    while True:
        messages = [{"role": "system", "content": system_prompt}, *history]
        response = complete(config, messages, tools=schemas)
        message = response.choices[0].message

        assistant_message: dict[str, Any] = {"role": "assistant", "content": message.content}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments},
                }
                for tool_call in tool_calls
            ]
        history.append(assistant_message)

        if not tool_calls:
            return message.content or ""

        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call.function.name)
            if tool is None:
                result: Any = {"error": f"Unknown tool: {tool_call.function.name!r}"}
            else:
                arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                result = tool.handler(arguments)
            history.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

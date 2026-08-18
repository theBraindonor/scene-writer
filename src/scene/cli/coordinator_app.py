from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from scene.agent.config import LLMConfig
from scene.agent.coordinator.loop import DEFAULT_SYSTEM_PROMPT, run_turn
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.story import build_story_tools
from scene.core.story import get_story
from scene.data.database import session_scope

NO_STORY_TEXT = "No current story yet.\n\nAsk the coordinator to create or open a story."

QUIT_COMMAND = "/quit"
CLEAR_COMMAND = "/clear"


class CoordinatorApp(App[None]):
    CSS = """
    Horizontal {
        height: 1fr;
    }

    #chat-column {
        width: 1fr;
        height: 1fr;
    }

    #story-column {
        width: 1fr;
        height: 1fr;
        border-left: solid $panel;
        padding: 1;
    }

    #chat-log {
        height: 1fr;
    }
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__()
        self.config = config
        self.state = CoordinatorState()
        self.tools = build_story_tools(self.state)
        self.chat_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="chat-column"):
                yield RichLog(id="chat-log", wrap=True, markup=False)
                yield Input(placeholder="Type a message, or /quit, /clear...", id="chat-input")
            with Vertical(id="story-column"):
                yield Static(NO_STORY_TEXT, id="story-pane")

    def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return

        text = event.value.strip()
        event.input.value = ""
        if not text:
            return

        if text.startswith("/"):
            self._handle_command(text)
            return

        self._append_chat(f"You: {text}")
        self._respond(text)

    def _handle_command(self, text: str) -> None:
        command = text.strip().lower()
        if command == QUIT_COMMAND:
            self.exit()
        elif command == CLEAR_COMMAND:
            self.state.history.clear()
            self.state.current_story_id = None
            self.chat_lines.clear()
            self.query_one("#chat-log", RichLog).clear()
            self._refresh_story_pane()
        else:
            self._append_chat(f"Unknown command: {text}")

    @work(thread=True)
    def _respond(self, user_message: str) -> None:
        reply = run_turn(
            self.config,
            self.state.history,
            user_message,
            tools=self.tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
        )
        self.call_from_thread(self._append_chat, f"Coordinator: {reply}")
        self.call_from_thread(self._refresh_story_pane)

    def _append_chat(self, text: str) -> None:
        self.chat_lines.append(text)
        self.query_one("#chat-log", RichLog).write(text)

    def _render_story_pane(self) -> str:
        story_id = self.state.current_story_id
        if story_id is None:
            return NO_STORY_TEXT

        with session_scope() as session:
            story = get_story(session, story_id)
            if story is None:
                return f"Story {story_id} not found."
            lines = [
                f"Story {story.id}: {story.title}",
                "",
                f"Scenario:\n{story.scenario}",
                "",
                f"Style guidance:\n{story.style_guidance or '(none)'}",
                "",
                f"Archived: {bool(story.is_archived)}",
            ]
            return "\n".join(lines)

    def _refresh_story_pane(self) -> None:
        self.query_one("#story-pane", Static).update(self._render_story_pane())

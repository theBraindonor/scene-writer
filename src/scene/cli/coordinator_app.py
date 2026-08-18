from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Markdown, Static, TextArea

from scene.agent.config import LLMConfig
from scene.agent.coordinator.loop import (
    DEFAULT_SYSTEM_PROMPT,
    ContentDelta,
    ReasoningDelta,
    ToolCallStarted,
    TurnComplete,
    TurnEvent,
    run_turn,
)
from scene.agent.coordinator.state import CoordinatorState
from scene.agent.coordinator.tools.character import build_character_tools
from scene.agent.coordinator.tools.scene import build_scene_tools
from scene.agent.coordinator.tools.story import build_story_tools
from scene.core.character import list_characters
from scene.core.scene import list_scenes
from scene.core.scene_character import list_characters_for_scene
from scene.core.story import get_story
from scene.data.database import session_scope

NO_STORY_TEXT = "No current story yet.\n\nAsk the coordinator to create or open a story."

QUIT_COMMAND = "/quit"
CLEAR_COMMAND = "/clear"

PROCESSING_TEXT = "⏳ Working..."
THINKING_EXPANDED_LABEL = "▾ Thinking"
THINKING_COLLAPSED_LABEL = "▸ Thinking"

# Most terminals cannot distinguish Shift+Enter from plain Enter without an extended
# keyboard protocol the terminal must opt into, so Ctrl+J (a genuinely distinct byte,
# line feed vs. carriage return) is offered as a reliable fallback for a newline.
NEWLINE_KEYS = {"shift+enter", "ctrl+j"}


class ChatInput(TextArea):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            text = self.text
            self.clear()
            self.post_message(self.Submitted(text))
            return
        if event.key in NEWLINE_KEYS:
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            return
        await super()._on_key(event)


class UserMessage(Vertical):
    def __init__(self, text: str) -> None:
        super().__init__(classes="message-block user-message")
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static("You", classes="message-label")
        yield Markdown(self._text)


class AgentTurnBlock(Vertical):
    def __init__(self) -> None:
        super().__init__(classes="message-block agent-turn")
        self._reasoning_text = ""
        self._answer_text = ""
        self._tool_names: list[str] = []
        self._thinking_expanded = False
        self._thinking_user_toggled = False

    def compose(self) -> ComposeResult:
        yield Static("Coordinator", classes="message-label")
        toggle = Button(THINKING_COLLAPSED_LABEL, id="thinking-toggle", variant="default", compact=True)
        toggle.display = False
        yield toggle
        thinking_text = Markdown("", id="thinking-text", classes="thinking-text")
        thinking_text.display = False
        yield thinking_text
        yield Static("", id="tool-calls", classes="tool-calls")
        yield Static(PROCESSING_TEXT, id="processing-indicator", classes="processing-indicator")
        yield Markdown("", id="answer-text")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "thinking-toggle":
            return
        event.stop()
        self._thinking_user_toggled = True
        self._thinking_expanded = not self._thinking_expanded
        self._apply_thinking_visibility()

    def _apply_thinking_visibility(self) -> None:
        self.query_one("#thinking-text", Markdown).display = self._thinking_expanded
        self.query_one("#thinking-toggle", Button).label = (
            THINKING_EXPANDED_LABEL if self._thinking_expanded else THINKING_COLLAPSED_LABEL
        )

    def _note_reasoning_ended(self) -> None:
        if self._reasoning_text and not self._thinking_user_toggled and self._thinking_expanded:
            self._thinking_expanded = False
            self._apply_thinking_visibility()

    def append_reasoning(self, text: str) -> None:
        first_time = not self._reasoning_text
        self._reasoning_text += text
        self.query_one("#thinking-text", Markdown).update(self._reasoning_text)
        if first_time:
            self.query_one("#thinking-toggle", Button).display = True
            if not self._thinking_user_toggled:
                self._thinking_expanded = True
            self._apply_thinking_visibility()
        self.query_one("#processing-indicator", Static).display = False

    def append_answer(self, text: str) -> None:
        self._note_reasoning_ended()
        self._answer_text += text
        self.query_one("#answer-text", Markdown).update(self._answer_text)
        self.query_one("#processing-indicator", Static).display = False

    def add_tool_call(self, name: str) -> None:
        self._note_reasoning_ended()
        self._tool_names.append(name)
        self.query_one("#tool-calls", Static).update("\n".join(f"🔧 {tool_name}" for tool_name in self._tool_names))
        self.query_one("#processing-indicator", Static).display = True

    def complete(self) -> None:
        self._note_reasoning_ended()
        self.query_one("#processing-indicator", Static).display = False


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

    #transcript {
        height: 1fr;
    }

    #chat-input {
        height: 4;
    }

    .message-block {
        height: auto;
        padding: 0 1;
        margin: 1 0;
    }

    .user-message {
        border-left: solid $primary;
    }

    .agent-turn {
        border-left: solid $accent;
    }

    .message-label {
        text-style: bold;
        color: $text-muted;
    }

    .thinking-text, .tool-calls {
        color: $text-muted;
    }

    /* Textual's built-in Markdown widget wraps every list item in a raw Horizontal
       container with no height override, so it inherits Horizontal's height: 1fr
       default. That's fine when Markdown fills a fixed-height pane, but inside our
       auto-height message blocks it blows each list item out to a large fraction
       of the available space. Force list-item rows back to their natural content
       height. */
    MarkdownOrderedList Horizontal, MarkdownBulletList Horizontal {
        height: auto;
    }

    .processing-indicator {
        color: $warning;
    }
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__()
        self.config = config
        self.state = CoordinatorState()
        self.tools = [
            *build_story_tools(self.state),
            *build_scene_tools(self.state),
            *build_character_tools(self.state),
        ]
        self._active_block: AgentTurnBlock | None = None

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="chat-column"):
                yield VerticalScroll(id="transcript")
                yield ChatInput(id="chat-input", placeholder="Type a message, or /quit, /clear...")
            with Vertical(id="story-column"):
                yield Static(NO_STORY_TEXT, id="story-pane")

    def on_mount(self) -> None:
        self.query_one("#chat-input", ChatInput).focus()

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        text = event.text.strip()
        if not text:
            return

        if text.startswith("/"):
            await self._handle_command(text)
            return

        await self.query_one("#transcript", VerticalScroll).mount(UserMessage(text))
        block = AgentTurnBlock()
        await self.query_one("#transcript", VerticalScroll).mount(block)
        self._active_block = block
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)
        self._respond(text)

    async def _handle_command(self, text: str) -> None:
        command = text.strip().lower()
        if command == QUIT_COMMAND:
            self.exit()
        elif command == CLEAR_COMMAND:
            self.state.history.clear()
            self.state.current_story_id = None
            await self.query_one("#transcript", VerticalScroll).remove_children()
            self._refresh_story_pane()
        else:
            await self.query_one("#transcript", VerticalScroll).mount(Static(f"Unknown command: {text}"))

    @work(thread=True)
    def _respond(self, user_message: str) -> None:
        block = self._active_block
        assert block is not None

        for event in run_turn(
            self.config,
            self.state.history,
            user_message,
            tools=self.tools,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
        ):
            self.call_from_thread(self._apply_turn_event, block, event)

        self.call_from_thread(self._refresh_story_pane)

    def _apply_turn_event(self, block: AgentTurnBlock, event: TurnEvent) -> None:
        if isinstance(event, ReasoningDelta):
            block.append_reasoning(event.text)
        elif isinstance(event, ContentDelta):
            block.append_answer(event.text)
        elif isinstance(event, ToolCallStarted):
            block.add_tool_call(event.name)
        elif isinstance(event, TurnComplete):
            block.complete()
        self.query_one("#transcript", VerticalScroll).scroll_end(animate=False)

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
                "",
                "Cast of characters:",
            ]
            characters = list_characters(session, story_id)
            if characters:
                for character in characters:
                    lines.append(f"  {character.name}")
                    lines.append(f"     Description: {character.description or '(none)'}")
                    lines.append(f"     Motive: {character.motive or '(none)'}")
            else:
                lines.append("  (none yet)")
            lines.append("")
            lines.append("Scenes:")
            scenes = list_scenes(session, story_id)
            if scenes:
                for scene in scenes:
                    lines.append(f"  {scene.position}. {scene.heading or '(untitled)'}")
                    lines.append(f"     Description: {scene.description}")
                    lines.append(f"     Required actions: {scene.required_actions or '(none)'}")
                    lines.append(f"     Length: {scene.length or '(unspecified)'}")
                    scene_characters = list_characters_for_scene(session, scene.id)
                    character_names = ", ".join(character.name for character in scene_characters) or "(none)"
                    lines.append(f"     Characters: {character_names}")
            else:
                lines.append("  (none yet)")
            return "\n".join(lines)

    def _refresh_story_pane(self) -> None:
        self.query_one("#story-pane", Static).update(self._render_story_pane())

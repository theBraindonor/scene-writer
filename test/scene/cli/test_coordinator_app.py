from dataclasses import dataclass, field

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, Markdown, Static

import scene.agent.coordinator.loop as loop_module
import scene.data.database as database_module
from scene.agent.config import LLMConfig
from scene.cli.coordinator_app import (
    AgentTurnBlock,
    ChatInput,
    CoordinatorApp,
    UserMessage,
)
from scene.core.character import list_characters
from scene.core.location import list_locations
from scene.core.scene import list_scenes
from scene.data.database import session_scope


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@dataclass
class FakeFunctionDelta:
    name: str | None = None
    arguments: str | None = None


@dataclass
class FakeToolCallDelta:
    index: int
    id: str | None = None
    function: FakeFunctionDelta | None = None


@dataclass
class FakeDelta:
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[FakeToolCallDelta] | None = None


@dataclass
class FakeChoice:
    delta: FakeDelta


@dataclass
class FakeChunk:
    choices: list[FakeChoice] = field(default_factory=list)


def make_chunk(content=None, reasoning_content=None, tool_calls=None):
    return FakeChunk(choices=[FakeChoice(delta=FakeDelta(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls))])


def script_stream(monkeypatch, rounds):
    rounds = [list(round_chunks) for round_chunks in rounds]

    def fake_stream_complete(config, messages, tools=None):
        return iter(rounds.pop(0))

    monkeypatch.setattr(loop_module, "stream_complete", fake_stream_complete)


def make_config():
    return LLMConfig(model="openai/test-model", api_base=None, api_key=None)


async def send(pilot, text):
    pilot.app.query_one("#chat-input", ChatInput).text = text
    await pilot.press("enter")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def agent_blocks(app):
    return list(app.query(AgentTurnBlock))


async def test_quit_command_exits_app():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "/quit")
        assert not app.is_running


async def test_unknown_slash_command_shows_notice():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "/bogus")
        notices = [str(s.content) for s in app.query("#transcript > Static")]
        assert notices == ["Unknown command: /bogus"]


async def test_blank_input_is_ignored():
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "   ")
        assert app.query("#transcript > *").__len__() == 0


async def test_plain_chat_turn_renders_user_and_agent_blocks(monkeypatch):
    script_stream(monkeypatch, [[make_chunk(content="Hello"), make_chunk(content=" there!")]])

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "hi")

        user_messages = list(app.query(UserMessage))
        assert len(user_messages) == 1
        assert user_messages[0].query_one(Markdown).source == "hi"

        blocks = agent_blocks(app)
        assert len(blocks) == 1
        assert blocks[0].query_one("#answer-text", Markdown).source == "Hello there!"
        assert blocks[0].query_one("#processing-indicator", Static).display is False
        assert app.state.history[-1] == {"role": "assistant", "content": "Hello there!"}


async def test_reasoning_expands_then_auto_collapses(monkeypatch):
    script_stream(
        monkeypatch,
        [[make_chunk(reasoning_content="Thinking about it..."), make_chunk(content="The answer.")]],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "hi")

        block = agent_blocks(app)[0]
        assert block.query_one("#thinking-text", Markdown).source == "Thinking about it..."
        toggle = block.query_one("#thinking-toggle", Button)
        assert toggle.display is True
        # Auto-collapsed once answer content started streaming.
        assert block.query_one("#thinking-text", Markdown).display is False


async def test_thinking_toggle_expands_and_stays_expanded(monkeypatch):
    script_stream(
        monkeypatch,
        [[make_chunk(reasoning_content="Thinking about it..."), make_chunk(content="The answer.")]],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "hi")

        block = agent_blocks(app)[0]
        assert block.query_one("#thinking-text", Markdown).display is False

        await pilot.click("#thinking-toggle")
        assert block.query_one("#thinking-text", Markdown).display is True

        # A later turn's streaming must not auto-collapse it again once user-toggled.
        script_stream(monkeypatch, [[make_chunk(content="Another reply.")]])
        await send(pilot, "again")
        assert block.query_one("#thinking-text", Markdown).display is True


async def test_tool_call_notice_shows_name_only(monkeypatch):
    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")

        block = agent_blocks(app)[0]
        tool_calls_text = str(block.query_one("#tool-calls", Static).content)
        assert "create_story" in tool_calls_text
        assert "New Story" not in tool_calls_text
        assert "A scenario" not in tool_calls_text


async def test_story_pane_updates_after_tool_call(monkeypatch):
    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")

        assert app.state.current_story_id is not None
        pane_text = str(app.query_one("#story-pane", Static).content)
        assert "New Story" in pane_text
        assert "A scenario" in pane_text


async def test_story_pane_shows_new_scene_after_tool_call(monkeypatch):
    story_tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    story_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}')
    )
    scene_tool_call = FakeToolCallDelta(index=0, id="call_2", function=FakeFunctionDelta(name="create_scene"))
    scene_args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(
            arguments=(
                '{"position": 0, "description": "Opening scene", "heading": "Arrival", '
                '"required_actions": "Introduce the protagonist", "length": "Short"}'
            )
        ),
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[story_tool_call]), make_chunk(tool_calls=[story_args])],
            [make_chunk(content="Created the story!")],
            [make_chunk(tool_calls=[scene_tool_call]), make_chunk(tool_calls=[scene_args])],
            [make_chunk(content="Added the scene!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")
        await send(pilot, "please add an opening scene")

        pane_text = str(app.query_one("#story-pane", Static).content)
        assert "Arrival" in pane_text
        assert "Opening scene" in pane_text
        assert "Introduce the protagonist" in pane_text
        assert "Short" in pane_text


async def test_story_pane_shows_character_in_cast_and_assigned_scene(monkeypatch):
    story_tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    story_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}')
    )
    scene_tool_call = FakeToolCallDelta(index=0, id="call_2", function=FakeFunctionDelta(name="create_scene"))
    scene_args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(arguments='{"position": 0, "description": "Opening scene", "heading": "Arrival"}'),
    )
    character_tool_call = FakeToolCallDelta(index=0, id="call_3", function=FakeFunctionDelta(name="create_character"))
    character_args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(
            arguments='{"name": "Alex", "description": "A wanderer", "motive": "Find home"}'
        ),
    )
    assign_tool_call = FakeToolCallDelta(index=0, id="call_4", function=FakeFunctionDelta(name="assign_character"))

    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[story_tool_call]), make_chunk(tool_calls=[story_args])],
            [make_chunk(content="Created the story!")],
            [make_chunk(tool_calls=[scene_tool_call]), make_chunk(tool_calls=[scene_args])],
            [make_chunk(content="Added the scene!")],
            [make_chunk(tool_calls=[character_tool_call]), make_chunk(tool_calls=[character_args])],
            [make_chunk(content="Added the character!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")
        await send(pilot, "please add an opening scene")
        await send(pilot, "please add a character named Alex")

        story_id = app.state.current_story_id
        with session_scope() as session:
            scene_id = list_scenes(session, story_id)[0].id
            character_id = list_characters(session, story_id)[0].id

        assign_args = FakeToolCallDelta(
            index=0,
            function=FakeFunctionDelta(arguments=f'{{"scene_id": {scene_id}, "character_id": {character_id}}}'),
        )
        script_stream(
            monkeypatch,
            [
                [make_chunk(tool_calls=[assign_tool_call]), make_chunk(tool_calls=[assign_args])],
                [make_chunk(content="Assigned!")],
            ],
        )
        await send(pilot, "please assign Alex to the opening scene")

        pane_text = str(app.query_one("#story-pane", Static).content)
        assert "Cast of characters:" in pane_text
        assert "Alex" in pane_text
        assert "Description: A wanderer" in pane_text
        assert "Motive: Find home" in pane_text
        assert "Characters: Alex" in pane_text


async def test_story_pane_shows_location_in_locations_and_assigned_scene(monkeypatch):
    story_tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    story_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}')
    )
    scene_tool_call = FakeToolCallDelta(index=0, id="call_2", function=FakeFunctionDelta(name="create_scene"))
    scene_args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(arguments='{"position": 0, "description": "Opening scene", "heading": "Arrival"}'),
    )
    location_tool_call = FakeToolCallDelta(index=0, id="call_3", function=FakeFunctionDelta(name="create_location"))
    location_args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(arguments='{"name": "The Tavern", "description": "A cozy inn"}'),
    )
    assign_tool_call = FakeToolCallDelta(index=0, id="call_4", function=FakeFunctionDelta(name="assign_location"))

    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[story_tool_call]), make_chunk(tool_calls=[story_args])],
            [make_chunk(content="Created the story!")],
            [make_chunk(tool_calls=[scene_tool_call]), make_chunk(tool_calls=[scene_args])],
            [make_chunk(content="Added the scene!")],
            [make_chunk(tool_calls=[location_tool_call]), make_chunk(tool_calls=[location_args])],
            [make_chunk(content="Added the location!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")
        await send(pilot, "please add an opening scene")
        await send(pilot, "please add a location called The Tavern")

        story_id = app.state.current_story_id
        with session_scope() as session:
            scene_id = list_scenes(session, story_id)[0].id
            location_id = list_locations(session, story_id)[0].id

        assign_args = FakeToolCallDelta(
            index=0,
            function=FakeFunctionDelta(arguments=f'{{"scene_id": {scene_id}, "location_id": {location_id}}}'),
        )
        script_stream(
            monkeypatch,
            [
                [make_chunk(tool_calls=[assign_tool_call]), make_chunk(tool_calls=[assign_args])],
                [make_chunk(content="Assigned!")],
            ],
        )
        await send(pilot, "please assign The Tavern to the opening scene")

        pane_text = str(app.query_one("#story-pane", Static).content)
        assert "Locations:" in pane_text
        assert "The Tavern" in pane_text
        assert "Description: A cozy inn" in pane_text
        assert "Locations: The Tavern" in pane_text


async def test_story_pane_shows_placeholder_until_a_story_exists():
    app = CoordinatorApp(make_config())
    async with app.run_test():
        assert "No current story" in str(app.query_one("#story-pane", Static).content)


async def test_clear_resets_history_current_story_transcript_and_pane(monkeypatch):
    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"title": "New Story", "scenario": "A scenario"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "please create a story")
        assert app.state.current_story_id is not None

        await send(pilot, "/clear")

        assert app.state.current_story_id is None
        assert app.state.history == []
        assert len(list(app.query("#transcript > *"))) == 0
        assert "No current story" in str(app.query_one("#story-pane", Static).content)


def test_newline_key_set_includes_ctrl_j():
    from scene.cli.coordinator_app import NEWLINE_KEYS

    assert "ctrl+j" in NEWLINE_KEYS
    assert "shift+enter" in NEWLINE_KEYS


async def test_ctrl_j_inserts_newline_instead_of_submitting(monkeypatch):
    def unexpected_stream_complete(config, messages, tools=None):
        raise AssertionError("stream_complete() should not be called for a newline key")

    monkeypatch.setattr(loop_module, "stream_complete", unexpected_stream_complete)

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        chat_input = app.query_one("#chat-input", ChatInput)
        chat_input.focus()
        await pilot.press("h", "i", "ctrl+j", "t", "h", "e", "r", "e")
        await pilot.pause()

        assert chat_input.text == "hi\nthere"
        assert len(list(app.query("#transcript > *"))) == 0


async def test_typing_a_printable_character_inserts_it(monkeypatch):
    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        chat_input = app.query_one("#chat-input", ChatInput)
        chat_input.focus()
        await pilot.press("x")
        await pilot.pause()

        assert chat_input.text == "x"


def test_on_button_pressed_ignores_unrelated_buttons():
    class FakeButton:
        id = "not-thinking-toggle"

    class FakeEvent:
        button = FakeButton()

        def stop(self):
            raise AssertionError("stop() should not be called for an unrelated button")

    block = AgentTurnBlock()
    block.on_button_pressed(FakeEvent())
    assert block._thinking_user_toggled is False


def test_render_story_pane_handles_missing_story():
    app = CoordinatorApp(make_config())
    app.state.current_story_id = 999

    assert "999" in app._render_story_pane()
    assert "not found" in app._render_story_pane()


async def test_message_blocks_stay_content_sized_and_transcript_scrolls(monkeypatch):
    script_stream(monkeypatch, [[make_chunk(content=f"Reply {i}.")] for i in range(6)])

    app = CoordinatorApp(make_config())
    async with app.run_test(size=(100, 40)) as pilot:
        for i in range(6):
            await send(pilot, f"message {i}")

        blocks = agent_blocks(app)
        assert len(blocks) == 6
        # A block's height must come from its own content ("auto"), not an equal
        # 1fr share of the transcript that shrinks every widget as more are added.
        for block in blocks:
            assert str(block.styles.height) == "auto"

        transcript = app.query_one("#transcript")
        assert transcript.virtual_size.height > transcript.size.height
        assert transcript.max_scroll_y > 0


async def test_chat_input_shows_at_least_two_content_rows():
    app = CoordinatorApp(make_config())
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        chat_input = app.query_one("#chat-input", ChatInput)
        assert chat_input.size.height >= 2


async def test_transcript_auto_scrolls_on_every_streamed_event(monkeypatch):
    script_stream(
        monkeypatch,
        [[make_chunk(content="a"), make_chunk(content="b"), make_chunk(content="c")]],
    )

    calls = []
    original_scroll_end = VerticalScroll.scroll_end

    def spy_scroll_end(self, *args, **kwargs):
        if self.id == "transcript":
            calls.append(1)
        return original_scroll_end(self, *args, **kwargs)

    monkeypatch.setattr(VerticalScroll, "scroll_end", spy_scroll_end)

    app = CoordinatorApp(make_config())
    async with app.run_test() as pilot:
        await send(pilot, "hi")

        # One scroll per streamed event (3 content deltas + TurnComplete), not just
        # a single scroll at the very end of the turn.
        assert calls.count(1) >= 4


async def test_ordered_list_does_not_blow_out_block_height(monkeypatch):
    script_stream(
        monkeypatch,
        [[make_chunk(content="A list:\n\n1. First item\n2. Second item\n3. Third item\n")]],
    )

    app = CoordinatorApp(make_config())
    async with app.run_test(size=(100, 40)) as pilot:
        await send(pilot, "give me a list")

        block = agent_blocks(app)[0]
        # Each list-item row should be its natural one-line content height, not an
        # equal 1fr share of whatever space Textual's Markdown widget happens to see.
        for row in block.query_one("#answer-text", Markdown).query("Horizontal"):
            assert row.size.height == 1
        assert block.region.height < 15

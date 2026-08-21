from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import Qt

import scene.agent.coordinator.loop as loop_module
import scene.data.database as database_module
import scene.gui.main_window as main_window_module
from scene.agent.config import LLMConfig
from scene.core.character import list_characters
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene, list_scenes
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.main_window import MainWindow
from scene.gui.rendering_column import NO_SCENE_SELECTED_TEXT


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture(autouse=True)
def working_llm_config(monkeypatch):
    monkeypatch.setattr(
        main_window_module, "get_llm_config", lambda role: LLMConfig(model="openai/test-model", api_base=None, api_key=None)
    )


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
    return FakeChunk(
        choices=[
            FakeChoice(delta=FakeDelta(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls))
        ]
    )


def script_stream(monkeypatch, rounds):
    rounds = [list(round_chunks) for round_chunks in rounds]

    def fake_stream_complete(config, messages, tools=None):
        return iter(rounds.pop(0))

    monkeypatch.setattr(loop_module, "stream_complete", fake_stream_complete)


def send(qtbot, window, text):
    window.chat_panel.input_edit.setText(text)
    with qtbot.waitSignal(window.chat_panel.turn_completed, timeout=2000):
        window.chat_panel.input_edit.returnPressed.emit()


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, scenario="A scenario")
        return story.id


def make_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    return window


def select_story(window, story_id):
    window.story_header.story_selected.emit(story_id)


def test_window_shows_placeholder_panes(qtbot):
    window = make_window(qtbot)

    assert window.entity_column.stack.currentWidget() is window.entity_column.empty_label
    assert window.rendering_column.stack.currentWidget() is window.rendering_column.no_selection_label
    assert window.rendering_column.no_selection_label.text() == NO_SCENE_SELECTED_TEXT
    assert window.chat_panel.input_edit.isEnabled()


def test_selecting_story_updates_current_story_id_and_emits_signal(qtbot):
    story_id = seed_story("A Story")
    window = make_window(qtbot)

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        select_story(window, story_id)

    assert blocker.args == [story_id]
    assert window.current_story_id == story_id
    assert window.entity_column.current_story_id == story_id


def test_creating_story_via_header_updates_window(qtbot, monkeypatch):
    window = make_window(qtbot)

    monkeypatch.setattr(window.story_header, "_prompt_new_story", lambda: ("New Story", "A scenario", None))

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        qtbot.mouseClick(window.story_header.new_story_button, Qt.MouseButton.LeftButton)

    assert window.current_story_id == blocker.args[0]
    assert window.story_header.story_label.text() == "New Story"


def test_selecting_scene_updates_rendering_column(qtbot):
    story_id = seed_story("A Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, description="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    select_story(window, story_id)

    with qtbot.waitSignal(window.entity_column.current_scene_changed, timeout=1000):
        window.entity_column.scenes.list_widget.setCurrentRow(0)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.body_view
    assert window.rendering_column.body_view.toPlainText() == "Once upon a time."


def test_switching_story_resets_rendering_column(qtbot):
    first_story_id = seed_story("First Story")
    second_story_id = seed_story("Second Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=first_story_id, position=0, description="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    select_story(window, first_story_id)
    window.entity_column.scenes.list_widget.setCurrentRow(0)
    assert window.rendering_column.stack.currentWidget() is window.rendering_column.body_view

    select_story(window, second_story_id)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.no_selection_label


def test_selecting_story_sets_coordinator_state(qtbot):
    story_id = seed_story("A Story")
    window = make_window(qtbot)

    select_story(window, story_id)

    assert window.coordinator_state.current_story_id == story_id


def test_chat_creating_story_updates_header_and_entity_column(qtbot, monkeypatch):
    window = make_window(qtbot)

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "Agent Story", "scenario": "A scenario"}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )

    send(qtbot, window, "please create a story")

    assert window.current_story_id == window.coordinator_state.current_story_id
    assert window.story_header.story_label.text() == "Agent Story"
    assert window.entity_column.current_story_id == window.current_story_id


def test_chat_editing_scene_refreshes_entity_column(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    with session_scope() as session:
        create_scene(session, story_id=story_id, position=0, description="Original description")

    window = make_window(qtbot)
    select_story(window, story_id)

    with session_scope() as session:
        scene_id = list_scenes(session, story_id)[0].id

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="update_scene"))
    args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(arguments=f'{{"scene_id": {scene_id}, "description": "Updated description"}}'),
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Updated it!")],
        ],
    )
    send(qtbot, window, "please update the scene's description")

    with session_scope() as session:
        assert list_scenes(session, story_id)[0].description == "Updated description"
    assert window.entity_column.scenes.list_widget.count() == 1


def test_chat_creating_character_refreshes_entity_column(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_character"))
    args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"name": "Alex"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Added!")],
        ],
    )

    send(qtbot, window, "please add a character named Alex")

    with session_scope() as session:
        assert len(list_characters(session, story_id)) == 1
    assert window.entity_column.characters.list_widget.count() == 1
    assert window.entity_column.characters.list_widget.item(0).text() == "Alex"

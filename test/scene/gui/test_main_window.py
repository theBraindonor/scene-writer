import threading
from dataclasses import dataclass, field

import pytest
import yaml
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

import scene.agent.coordinator.loop as loop_module
import scene.data.database as database_module
import scene.gui.main_window as main_window_module
import scene.gui.rendering_column as rendering_column_module
from scene.agent.config import LLMConfig
from scene.agent.continuity import ContinuitySceneComplete, ContinuitySceneStarted
from scene.agent.rendering import RenderComplete, RenderContentDelta
from scene.agent.role import AgentRole
from scene.core.character import list_characters
from scene.core.continuity_snapshot import create_snapshot, get_snapshot
from scene.core.location import create_location, get_location
from scene.core.rendering import create_rendering, list_renderings, set_active_rendering
from scene.core.scene import create_scene, get_scene
from scene.core.story import create_story, list_stories
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


def send(qtbot, window, text, timeout=2000):
    window.chat_panel.input_edit.setText(text)
    with qtbot.waitSignal(window.chat_panel.turn_completed, timeout=timeout):
        window.chat_panel.input_edit.returnPressed.emit()


def seed_story(title="A Story"):
    with session_scope() as session:
        story = create_story(session, title=title, story_brief="A story brief")
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


def test_rendering_column_receives_resolved_continuity_config(qtbot):
    window = make_window(qtbot)

    assert window.rendering_column._llm_config is not None
    assert window.rendering_column._continuity_config is not None


def test_missing_continuity_config_does_not_disable_generation(qtbot, monkeypatch):
    def selective_get_llm_config(role):
        if role is AgentRole.CONTINUITY_EDITING:
            raise RuntimeError("SCENE_CONTINUITY_AGENT is not set.")
        return LLMConfig(model="openai/test-model", api_base=None, api_key=None)

    monkeypatch.setattr(main_window_module, "get_llm_config", selective_get_llm_config)

    window = make_window(qtbot)

    assert window.rendering_column._llm_config is not None
    assert window.rendering_column._continuity_config is None
    assert "SCENE_CONTINUITY_AGENT is not set." in window.rendering_column.notice_label.text()


def test_left_column_composition(qtbot):
    window = make_window(qtbot)

    assert window.story_header.parentWidget() is window.left_column
    assert window.entity_column.parentWidget() is window.vertical_splitter
    assert window.chat_panel.parentWidget() is window.vertical_splitter
    assert window.vertical_splitter.parentWidget() is window.left_column


def test_horizontal_splitter_defaults_to_even_split_and_survives_resizes(qtbot):
    # Widths chosen comfortably above both panes' content-driven minimum width (~700px
    # combined), so the even split isn't fighting a minimum-size floor on either side.
    window = make_window(qtbot)

    for width in (1300, 1600):
        window.resize(width, 600)
        sizes = window.splitter.sizes()
        assert abs(sizes[0] - sizes[1]) <= 4


def test_dragging_horizontal_splitter_persists_across_resizes(qtbot):
    window = make_window(qtbot)
    window.resize(1400, 600)

    window.splitter.moveSplitter(500, 1)
    assert window._horizontal_manually_adjusted
    dragged_sizes = window.splitter.sizes()
    assert abs(dragged_sizes[0] - dragged_sizes[1]) > 100

    window.resize(1800, 600)

    # The drag should still dominate: the split stays clearly uneven rather than snapping back
    # to an even 900/900, though Qt's own proportional resize behavior means the exact pixel
    # values may shift somewhat as the window grows.
    sizes = window.splitter.sizes()
    assert abs(sizes[0] - sizes[1]) > 100


def test_entity_column_receives_extra_vertical_space_over_chat_panel(qtbot):
    story_id = seed_story("A Story")
    window = make_window(qtbot)

    select_story(window, story_id)

    assert window.entity_column.height() > window.chat_panel.height()


def test_chat_panel_height_stays_pinned_across_resizes_until_dragged(qtbot):
    window = make_window(qtbot)
    window.resize(1400, 800)

    initial_chat_height = window.chat_panel.height()

    window.resize(1400, 1000)
    assert window.chat_panel.height() == initial_chat_height

    window.vertical_splitter.moveSplitter(600, 1)
    dragged_chat_height = window.chat_panel.height()
    assert dragged_chat_height != initial_chat_height

    window.resize(1400, 1200)
    assert window.chat_panel.height() == dragged_chat_height


def test_collapsing_chat_panel_gives_its_space_to_entity_column(qtbot):
    window = make_window(qtbot)
    window.resize(1400, 800)

    expanded_entity_height = window.entity_column.height()
    expanded_chat_height = window.chat_panel.height()

    window.chat_panel.toggle_button.setChecked(False)

    assert window.chat_panel.height() < expanded_chat_height
    assert window.entity_column.height() > expanded_entity_height

    window.chat_panel.toggle_button.setChecked(True)

    assert window.chat_panel.height() == expanded_chat_height
    assert window.entity_column.height() == expanded_entity_height


def test_collapsing_chat_panel_restores_a_manually_dragged_height_on_expand(qtbot):
    window = make_window(qtbot)
    window.resize(1400, 800)

    window.vertical_splitter.moveSplitter(400, 1)
    dragged_chat_height = window.chat_panel.height()

    window.chat_panel.toggle_button.setChecked(False)
    window.chat_panel.toggle_button.setChecked(True)

    assert window.chat_panel.height() == dragged_chat_height


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
        scene = create_scene(session, story_id=story_id, position=0, brief="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    select_story(window, story_id)

    with qtbot.waitSignal(window.entity_column.current_scene_changed, timeout=1000):
        window.entity_column.scenes.list_widget.setCurrentRow(0)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.content_widget
    assert window.rendering_column.body_view.toPlainText() == "Once upon a time."


def test_switching_story_resets_rendering_column(qtbot):
    first_story_id = seed_story("First Story")
    second_story_id = seed_story("Second Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=first_story_id, position=0, brief="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    window = make_window(qtbot)
    select_story(window, first_story_id)
    window.entity_column.scenes.list_widget.setCurrentRow(0)
    assert window.rendering_column.stack.currentWidget() is window.rendering_column.content_widget

    select_story(window, second_story_id)

    assert window.rendering_column.stack.currentWidget() is window.rendering_column.no_selection_label


def test_selecting_story_sets_application_state(qtbot):
    story_id = seed_story("A Story")
    window = make_window(qtbot)

    select_story(window, story_id)

    assert window.application_state.current_story_id == story_id


def test_chat_creating_story_updates_header_and_entity_column(qtbot, monkeypatch):
    window = make_window(qtbot)

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_story"))
    args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"title": "Agent Story", "story_brief": "A scenario"}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Created it!")],
        ],
    )

    send(qtbot, window, "please create a story")

    assert window.current_story_id == window.application_state.current_story_id
    assert window.story_header.story_label.text() == "Agent Story"
    assert window.entity_column.current_story_id == window.current_story_id
    assert window.entity_column.tabs.currentIndex() == window.entity_column._STORY_TAB_INDEX


def test_chat_creating_character_refreshes_entity_column(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)
    window.entity_column.tabs.setCurrentIndex(window.entity_column._LOCATIONS_TAB_INDEX)

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
        characters = list_characters(session, story_id)
        assert len(characters) == 1
        character_id = characters[0].id
    assert window.entity_column.tabs.currentIndex() == window.entity_column._CHARACTERS_TAB_INDEX
    assert window.entity_column.characters.list_widget.count() == 1
    assert window.entity_column.characters.list_widget.item(0).text() == "Alex"
    assert window.entity_column.characters.current_character_id == character_id


def test_chat_updating_location_switches_to_locations_tab(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    with session_scope() as session:
        location = create_location(session, story_id=story_id, name="Old Name")
        location_id = location.id

    window = make_window(qtbot)
    select_story(window, story_id)
    window.entity_column.tabs.setCurrentIndex(window.entity_column._STORY_TAB_INDEX)

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="update_location"))
    args = FakeToolCallDelta(
        index=0,
        function=FakeFunctionDelta(arguments=f'{{"location_id": {location_id}, "name": "New Name"}}'),
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Renamed it!")],
        ],
    )

    send(qtbot, window, "please rename the location")

    with session_scope() as session:
        assert get_location(session, location_id).name == "New Name"
    assert window.entity_column.tabs.currentIndex() == window.entity_column._LOCATIONS_TAB_INDEX
    assert window.entity_column.locations.current_location_id == location_id


def test_chat_creating_scene_selects_it_and_switches_to_scenes_tab(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)

    tool_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_scene"))
    args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"brief": "A new scene"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[tool_call]), make_chunk(tool_calls=[args])],
            [make_chunk(content="Added!")],
        ],
    )

    send(qtbot, window, "please add a scene")

    assert window.entity_column.tabs.currentIndex() == window.entity_column._SCENES_TAB_INDEX
    assert window.application_state.current_scene_id is not None
    assert window.entity_column.scenes.current_scene_id == window.application_state.current_scene_id


def test_chat_scene_selection_persists_across_an_intervening_turn(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)

    create_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_scene"))
    create_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"brief": "The opening scene"}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[create_call]), make_chunk(tool_calls=[create_args])],
            [make_chunk(content="Added!")],
        ],
    )
    send(qtbot, window, "please add a scene")
    scene_id = window.application_state.current_scene_id
    assert scene_id is not None

    character_call = FakeToolCallDelta(index=0, id="call_2", function=FakeFunctionDelta(name="create_character"))
    character_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"name": "Zara"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[character_call]), make_chunk(tool_calls=[character_args])],
            [make_chunk(content="Added!")],
        ],
    )
    send(qtbot, window, "please add a character named Zara")

    # The Characters tab is now visible, but the scene selected two turns ago must still be
    # tracked, both in application state and in the (currently hidden) Scenes widget itself.
    assert window.entity_column.tabs.currentIndex() == window.entity_column._CHARACTERS_TAB_INDEX
    assert window.application_state.current_scene_id == scene_id
    assert window.entity_column.scenes.current_scene_id == scene_id

    update_call = FakeToolCallDelta(index=0, id="call_3", function=FakeFunctionDelta(name="update_scene"))
    update_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments='{"brief": "Updated via chat"}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[update_call]), make_chunk(tool_calls=[update_args])],
            [make_chunk(content="Updated!")],
        ],
    )
    send(qtbot, window, "please update the scene's brief")

    with session_scope() as session:
        assert get_scene(session, scene_id).brief == "Updated via chat"
    assert window.entity_column.tabs.currentIndex() == window.entity_column._SCENES_TAB_INDEX
    assert window.entity_column.scenes.current_scene_id == scene_id


def test_chat_opening_different_story_clears_scene_selection(qtbot, monkeypatch):
    first_story_id = seed_story("First Story")
    seed_story("Second Story")
    window = make_window(qtbot)
    select_story(window, first_story_id)

    create_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="create_scene"))
    create_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments='{"brief": "A scene"}'))
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[create_call]), make_chunk(tool_calls=[create_args])],
            [make_chunk(content="Added!")],
        ],
    )
    send(qtbot, window, "please add a scene")
    assert window.application_state.current_scene_id is not None

    with session_scope() as session:
        second_story_id = next(story.id for story in list_stories(session) if story.title == "Second Story")

    open_call = FakeToolCallDelta(index=0, id="call_2", function=FakeFunctionDelta(name="open_story"))
    open_args = FakeToolCallDelta(
        index=0, function=FakeFunctionDelta(arguments=f'{{"story_id": {second_story_id}}}')
    )
    script_stream(
        monkeypatch,
        [
            [make_chunk(tool_calls=[open_call]), make_chunk(tool_calls=[open_args])],
            [make_chunk(content="Opened!")],
        ],
    )
    send(qtbot, window, "please open the second story")

    assert window.application_state.current_scene_id is None


def test_chat_opening_a_story_and_selecting_a_scene_in_the_same_turn(qtbot, monkeypatch):
    # Regression test: MainWindow._on_chat_turn_completed used to unconditionally re-clear
    # application_state.current_scene_id whenever the open story changed during a turn (by
    # delegating to _on_story_selected), even if a *later* tool call in that same turn (like
    # select_scene, here) had already set a real selection after open_story ran. That silently
    # discarded the selection the person asked for whenever "open a story and select a scene"
    # happened in one message.
    story_id = seed_story("A Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, brief="The only scene")
        scene_id = scene.id

    window = make_window(qtbot)

    open_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="open_story"))
    open_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments=f'{{"story_id": {story_id}}}'))
    select_call = FakeToolCallDelta(index=1, id="call_2", function=FakeFunctionDelta(name="select_scene"))
    select_args = FakeToolCallDelta(index=1, function=FakeFunctionDelta(arguments=f'{{"scene_id": {scene_id}}}'))
    script_stream(
        monkeypatch,
        [
            [
                make_chunk(tool_calls=[open_call]),
                make_chunk(tool_calls=[open_args]),
                make_chunk(tool_calls=[select_call]),
                make_chunk(tool_calls=[select_args]),
            ],
            [make_chunk(content="Opened the story and selected its first scene.")],
        ],
    )

    send(qtbot, window, "please open the story and select its first scene")

    assert window.application_state.current_story_id == story_id
    assert window.application_state.current_scene_id == scene_id
    assert window.entity_column.tabs.currentIndex() == window.entity_column._SCENES_TAB_INDEX
    assert window.entity_column.scenes.current_scene_id == scene_id


def _fake_render_stream(events):
    def _stream(config, messages):
        yield from events

    return _stream


def _fake_accept_scene(events, narrative_state="New narrative state."):
    def _stream(config, session, story_id, scene_id):
        yield ContinuitySceneStarted(scene_id)
        yield from events
        snapshot = create_snapshot(session, story_id, scene_id, narrative_state)
        yield ContinuitySceneComplete(scene_id, snapshot)

    return _stream


def _render_scene_call(call_id="call_1"):
    render_call = FakeToolCallDelta(index=0, id=call_id, function=FakeFunctionDelta(name="render_scene"))
    render_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments="{}"))
    return [make_chunk(tool_calls=[render_call]), make_chunk(tool_calls=[render_args])]


def test_chat_rendering_scene_streams_live_and_persists(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    with session_scope() as session:
        first = create_scene(session, story_id=story_id, position=0, brief="First scene")
        rendering = create_rendering(session, scene_id=first.id, body="First scene prose.")
        set_active_rendering(session, rendering.id)
        second = create_scene(session, story_id=story_id, position=1, brief="Second scene")
        second_id = second.id

    window = make_window(qtbot)
    select_story(window, story_id)
    window.application_state.current_scene_id = second_id
    # Show a different tab so switching to Scenes is a real, observable effect of the render.
    window.entity_column.show_story_tab()

    monkeypatch.setattr(
        rendering_column_module,
        "stream_render",
        _fake_render_stream([RenderContentDelta("The chat-driven prose."), RenderComplete("The chat-driven prose.")]),
    )
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene([]))

    script_stream(monkeypatch, [_render_scene_call(), [make_chunk(content="Here it is!")]])

    send(qtbot, window, "please render the second scene", timeout=5000)

    assert window.entity_column.tabs.currentIndex() == window.entity_column._SCENES_TAB_INDEX
    with session_scope() as session:
        renderings = list_renderings(session, second_id)
        assert len(renderings) == 1
        assert renderings[0].is_active
        assert renderings[0].body == "The chat-driven prose."
        snapshot = get_snapshot(session, story_id, second_id)
        assert snapshot is not None
        assert snapshot.narrative_state == "New narrative state."
    assert window.rendering_column.body_view.toPlainText() == "The chat-driven prose."
    assert window.rendering_column.current_scene_id == second_id


def test_chat_ui_syncs_after_each_tool_call_not_just_at_turn_end(qtbot, monkeypatch):
    # Regression test: opening a story, selecting a scene, and rendering it all in one message
    # used to leave the story header and entity column showing stale/empty state until the
    # *entire* turn (including the render) finished, even though open_story and select_scene
    # had already completed and the render was visibly streaming. MainWindow only resynced once,
    # at turn_completed. It should resync after each tool call instead.
    story_id = seed_story("A Story")
    with session_scope() as session:
        first = create_scene(session, story_id=story_id, position=0, brief="First scene")
        rendering = create_rendering(session, scene_id=first.id, body="First scene prose.")
        set_active_rendering(session, rendering.id)
        second = create_scene(session, story_id=story_id, position=1, brief="Second scene")
        second_id = second.id

    window = make_window(qtbot)
    assert window.current_story_id is None

    gate = threading.Event()

    def _stream(config, messages):
        yield RenderContentDelta("Partial ")
        gate.wait(timeout=2)
        yield RenderContentDelta("prose.")
        yield RenderComplete("Partial prose.")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene([]))

    open_call = FakeToolCallDelta(index=0, id="call_1", function=FakeFunctionDelta(name="open_story"))
    open_args = FakeToolCallDelta(index=0, function=FakeFunctionDelta(arguments=f'{{"story_id": {story_id}}}'))
    select_call = FakeToolCallDelta(index=1, id="call_2", function=FakeFunctionDelta(name="select_scene"))
    select_args = FakeToolCallDelta(index=1, function=FakeFunctionDelta(arguments=f'{{"scene_id": {second_id}}}'))
    script_stream(
        monkeypatch,
        [
            [
                make_chunk(tool_calls=[open_call]),
                make_chunk(tool_calls=[open_args]),
                make_chunk(tool_calls=[select_call]),
                make_chunk(tool_calls=[select_args]),
            ],
            _render_scene_call(call_id="call_3"),
            [make_chunk(content="All done!")],
        ],
    )

    window.chat_panel.input_edit.setText("open the story, select the second scene, and render it")
    with qtbot.waitSignal(window.chat_panel.turn_completed, timeout=5000):
        window.chat_panel.input_edit.returnPressed.emit()
        # The render is now gated mid-stream -- open_story and select_scene have already
        # completed and returned, so their post-tool-call sync should already have landed,
        # well before the turn (and the render inside it) finishes.
        qtbot.waitUntil(lambda: window.rendering_column.body_view.toPlainText() == "Partial ", timeout=2000)
        assert window.current_story_id == story_id
        assert window.story_header.story_label.text() == "A Story"
        assert window.entity_column.current_story_id == story_id
        assert window.entity_column.tabs.currentIndex() == window.entity_column._SCENES_TAB_INDEX
        assert window.entity_column.scenes.current_scene_id == second_id
        gate.set()

    assert window.application_state.current_scene_id == second_id


def test_chat_cancelling_a_live_render_reports_cancellation_and_does_not_hang(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, brief="Only scene")
        scene_id = scene.id

    window = make_window(qtbot)
    select_story(window, story_id)
    window.application_state.current_scene_id = scene_id

    gate = threading.Event()

    def _stream(config, messages):
        yield RenderContentDelta("Partial ")
        gate.wait(timeout=2)
        yield RenderContentDelta("text.")
        yield RenderComplete("Partial text.")

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes))

    def unexpected_accept_scene(config, session, story_id, scene_id):
        raise AssertionError("stream_accept_scene() should not be called for a cancelled generation")
        yield  # pragma: no cover - never reached, keeps this a generator function

    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", unexpected_accept_scene)

    script_stream(monkeypatch, [_render_scene_call(), [make_chunk(content="Understood, cancelled.")]])

    window.chat_panel.input_edit.setText("please render this scene")
    with qtbot.waitSignal(window.chat_panel.turn_completed, timeout=5000):
        window.chat_panel.input_edit.returnPressed.emit()
        qtbot.waitUntil(lambda: window.rendering_column.body_view.toPlainText() == "Partial ", timeout=2000)
        window.rendering_column.cancel_button.click()
        gate.set()

    assert window.chat_panel.input_edit.isEnabled()
    with session_scope() as session:
        renderings = list_renderings(session, scene_id)
        assert len(renderings) == 1
        assert renderings[0].body == "Partial "


def find_menu(window, title):
    for action in window.menuBar().actions():
        if action.text() == title:
            return action.menu()
    raise AssertionError(f"No menu titled {title!r}")


def find_action(menu, text):
    for action in menu.actions():
        if action.text() == text:
            return action
    raise AssertionError(f"No action titled {text!r}")


def test_menu_bar_has_file_render_and_help_menus(qtbot):
    window = make_window(qtbot)

    titles = [action.text() for action in window.menuBar().actions()]
    assert titles == ["&File", "&Render", "&Help"]


def test_file_menu_new_story_action_creates_a_story(qtbot, monkeypatch):
    window = make_window(qtbot)
    monkeypatch.setattr(window.story_header, "_prompt_new_story", lambda: ("New Story", "A scenario", None))

    with qtbot.waitSignal(window.current_story_changed, timeout=1000):
        find_action(find_menu(window, "&File"), "&New Story...").trigger()

    assert window.story_header.story_label.text() == "New Story"


def test_file_menu_open_story_action_opens_the_selected_story(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    monkeypatch.setattr(window.story_header, "_prompt_story_picker", lambda: story_id)

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        find_action(find_menu(window, "&File"), "&Open Story...").trigger()

    assert blocker.args == [story_id]


def test_file_menu_exit_action_closes_the_window(qtbot):
    window = make_window(qtbot)
    assert window.isVisible()

    find_action(find_menu(window, "&File"), "E&xit").trigger()

    assert not window.isVisible()


def test_file_menu_has_new_open_export_import_and_exit_actions(qtbot):
    window = make_window(qtbot)

    titles = [action.text() for action in find_menu(window, "&File").actions() if not action.isSeparator()]
    assert titles == ["&New Story...", "&Open Story...", "&Export Story...", "&Import Story...", "E&xit"]


def test_export_story_with_no_story_selected_shows_message(qtbot, monkeypatch):
    window = make_window(qtbot)
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&File"), "&Export Story...").trigger()

    assert seen == [("Export Story", "Select a story first.")]


def test_export_story_saves_export_data(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)

    with session_scope() as session:
        expected = main_window_module.build_story_export_data(session, story_id)

    save_calls = []
    monkeypatch.setattr(main_window_module, "save_yaml_to_file", lambda parent, data: save_calls.append(data))

    find_action(find_menu(window, "&File"), "&Export Story...").trigger()

    assert save_calls == [expected]


def write_export_file(tmp_path, story_id, title=None, name="story.yaml"):
    with session_scope() as session:
        data = main_window_module.build_story_export_data(session, story_id)
    if title is not None:
        data["story"]["title"] = title
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_import_story_with_cancelled_file_dialog_does_nothing(qtbot, monkeypatch):
    window = make_window(qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))

    find_action(find_menu(window, "&File"), "&Import Story...").trigger()

    with session_scope() as session:
        assert list_stories(session) == []


def test_import_story_with_invalid_file_shows_error(qtbot, monkeypatch, tmp_path):
    window = make_window(qtbot)
    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text("not: [a, valid, export", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(bad_path), ""))
    seen = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&File"), "&Import Story...").trigger()

    assert seen and seen[0][0] == "Import Story"
    with session_scope() as session:
        assert list_stories(session) == []


def test_import_story_without_title_conflict_imports_and_selects_the_story(qtbot, monkeypatch, tmp_path):
    template_story_id = seed_story("Template Story")
    with session_scope() as session:
        create_scene(session, story_id=template_story_id, position=0, brief="Opening")
    path = write_export_file(tmp_path, template_story_id, title="Imported Story")

    window = make_window(qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (path, ""))

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        find_action(find_menu(window, "&File"), "&Import Story...").trigger()

    new_story_id = blocker.args[0]
    assert new_story_id != template_story_id
    assert window.current_story_id == new_story_id
    with session_scope() as session:
        titles = {story.title for story in list_stories(session)}
    assert titles == {"Template Story", "Imported Story"}


def test_import_story_with_title_conflict_prompts_and_imports_under_new_title(qtbot, monkeypatch, tmp_path):
    existing_story_id = seed_story("A Story")
    export_source_id = seed_story("Export Source")
    with session_scope() as session:
        create_scene(session, story_id=export_source_id, position=0, brief="Opening")
    path = write_export_file(tmp_path, export_source_id, title="A Story")

    window = make_window(qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (path, ""))

    class FakeDialog:
        def __init__(self, title, parent):
            self._title = title

        def exec(self):
            return QDialog.DialogCode.Accepted

        def new_title(self):
            return "A Story (2)"

    monkeypatch.setattr(main_window_module, "DuplicateStoryTitleDialog", FakeDialog)

    with qtbot.waitSignal(window.current_story_changed, timeout=1000) as blocker:
        find_action(find_menu(window, "&File"), "&Import Story...").trigger()

    new_story_id = blocker.args[0]
    assert new_story_id != existing_story_id
    with session_scope() as session:
        titles = {story.title for story in list_stories(session)}
    assert titles == {"A Story", "Export Source", "A Story (2)"}


def test_import_story_title_conflict_cancelled_aborts_import(qtbot, monkeypatch, tmp_path):
    seed_story("A Story")
    export_source_id = seed_story("Export Source")
    with session_scope() as session:
        create_scene(session, story_id=export_source_id, position=0, brief="Opening")
    path = write_export_file(tmp_path, export_source_id, title="A Story")

    window = make_window(qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (path, ""))

    class FakeDialog:
        def __init__(self, title, parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_module, "DuplicateStoryTitleDialog", FakeDialog)

    find_action(find_menu(window, "&File"), "&Import Story...").trigger()

    assert window.current_story_id is None
    with session_scope() as session:
        titles = {story.title for story in list_stories(session)}
    assert titles == {"A Story", "Export Source"}


def seed_rendered_story():
    story_id = seed_story("A Story")
    with session_scope() as session:
        scene = create_scene(session, story_id=story_id, position=0, brief="Opening")
        rendering = create_rendering(session, scene_id=scene.id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)
    return story_id


def test_render_menu_has_render_view_and_save_full_story_actions(qtbot):
    window = make_window(qtbot)

    titles = [action.text() for action in find_menu(window, "&Render").actions()]
    assert titles == ["&Render Full Story...", "&View Full Story...", "&Save Full Story..."]


def test_view_full_story_with_no_story_selected_shows_message(qtbot, monkeypatch):
    window = make_window(qtbot)
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&Render"), "&View Full Story...").trigger()

    assert seen == [("View Full Story", "Select a story first.")]


def test_save_full_story_with_no_story_selected_shows_message(qtbot, monkeypatch):
    window = make_window(qtbot)
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&Render"), "&Save Full Story...").trigger()

    assert seen == [("Save Full Story", "Select a story first.")]


def test_view_full_story_opens_dialog_with_combined_prose(qtbot, monkeypatch):
    story_id = seed_rendered_story()
    window = make_window(qtbot)
    select_story(window, story_id)

    seen = []

    class FakeDialog:
        def __init__(self, text, parent):
            seen.append(text)

        def exec(self):
            return None

    monkeypatch.setattr(main_window_module, "FullStoryDialog", FakeDialog)

    find_action(find_menu(window, "&Render"), "&View Full Story...").trigger()

    assert seen == ["Once upon a time."]


def test_save_full_story_saves_combined_prose_without_opening_viewer(qtbot, monkeypatch):
    story_id = seed_rendered_story()
    window = make_window(qtbot)
    select_story(window, story_id)

    save_calls = []
    monkeypatch.setattr(main_window_module, "save_text_to_file", lambda parent, text: save_calls.append(text))
    monkeypatch.setattr(
        main_window_module,
        "FullStoryDialog",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("viewer should not open")),
    )

    find_action(find_menu(window, "&Render"), "&Save Full Story...").trigger()


def test_render_full_story_with_no_story_selected_shows_message(qtbot, monkeypatch):
    window = make_window(qtbot)
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&Render"), "&Render Full Story...").trigger()

    assert seen == [("Render Full Story", "Select a story first.")]


def test_render_full_story_with_no_scenes_shows_message(qtbot, monkeypatch):
    story_id = seed_story("A Story")
    window = make_window(qtbot)
    select_story(window, story_id)
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&Render"), "&Render Full Story...").trigger()

    assert seen == [("Render Full Story", "This story has no scenes.")]


def test_render_full_story_with_rendering_not_configured_shows_message(qtbot, monkeypatch):
    story_id = seed_rendered_story()
    window = make_window(qtbot)
    select_story(window, story_id)
    window.rendering_column._llm_config = None
    seen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: seen.append(args[1:]))

    find_action(find_menu(window, "&Render"), "&Render Full Story...").trigger()

    assert seen == [("Render Full Story", "Rendering is not configured. See the Rendering panel for details.")]


def test_render_full_story_confirm_dialog_cancel_is_a_noop(qtbot, monkeypatch):
    story_id = seed_rendered_story()
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(
        main_window_module.RenderFullStoryConfirmDialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    monkeypatch.setattr(
        main_window_module,
        "FullStoryRenderController",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("controller should not start")),
    )

    find_action(find_menu(window, "&Render"), "&Render Full Story...").trigger()

    assert window.render_full_story_action.isEnabled()


def test_render_full_story_proceed_starts_controller_and_toggles_action(qtbot, monkeypatch):
    story_id = seed_rendered_story()
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(
        main_window_module.RenderFullStoryConfirmDialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )

    class FakeController(QObject):
        finished = Signal()

        def __init__(self, main_window):
            super().__init__(main_window)
            self.started_with = None

        def start(self, story_id):
            self.started_with = story_id

    monkeypatch.setattr(main_window_module, "FullStoryRenderController", FakeController)

    find_action(find_menu(window, "&Render"), "&Render Full Story...").trigger()

    controller = window._full_story_render_controller
    assert isinstance(controller, FakeController)
    assert controller.started_with == story_id
    assert not window.render_full_story_action.isEnabled()

    controller.finished.emit()

    assert window._full_story_render_controller is None
    assert window.render_full_story_action.isEnabled()


def test_help_menu_about_action_shows_about_dialog(qtbot, monkeypatch):
    window = make_window(qtbot)
    shown = []
    monkeypatch.setattr(main_window_module.AboutDialog, "exec", lambda self: shown.append(True))

    find_action(find_menu(window, "&Help"), "&About Scene Writer").trigger()

    assert shown == [True]

import threading
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QMessageBox

import scene.data.database as database_module
import scene.gui.main_window as main_window_module
import scene.gui.rendering_column as rendering_column_module
from scene.agent.config import LLMConfig
from scene.agent.continuity import ContinuityEvent, ContinuitySceneComplete, ContinuitySceneStarted
from scene.agent.rendering import RenderComplete, RenderContentDelta, RenderEvent
from scene.core.continuity_snapshot import create_snapshot
from scene.core.rendering import list_renderings
from scene.core.scene import create_scene, delete_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.full_story_render import FullStoryRenderController, RenderFullStoryConfirmDialog
from scene.gui.main_window import MainWindow


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


@pytest.fixture(autouse=True)
def working_llm_config(monkeypatch):
    monkeypatch.setattr(
        main_window_module, "get_llm_config", lambda role: LLMConfig(model="openai/test-model", api_base=None, api_key=None)
    )


def make_window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(900, 600)
    window.show()
    return window


def select_story(window, story_id):
    window.story_header.story_selected.emit(story_id)


def seed_story_with_scenes(count):
    with session_scope() as session:
        story = create_story(session, title="A Story", story_brief="A story brief")
        scene_ids = [create_scene(session, story_id=story.id, position=i, brief=f"Scene {i}").id for i in range(count)]
        return story.id, scene_ids


def _fake_stream(body):
    def _stream(config, messages) -> Iterator[RenderEvent]:
        yield RenderContentDelta(body)
        yield RenderComplete(body)

    return _stream


def _fake_accept_scene(config, session, story_id, scene_id) -> Iterator[ContinuityEvent]:
    yield ContinuitySceneStarted(scene_id)
    snapshot = create_snapshot(session, story_id, scene_id, "Fresh state.")
    yield ContinuitySceneComplete(scene_id, snapshot)


def test_confirm_dialog_cancel_rejects(qtbot):
    dialog = RenderFullStoryConfirmDialog()
    qtbot.addWidget(dialog)

    dialog.cancel_button.click()

    assert dialog.result() == dialog.DialogCode.Rejected


def test_confirm_dialog_proceed_accepts(qtbot):
    dialog = RenderFullStoryConfirmDialog()
    qtbot.addWidget(dialog)

    dialog.proceed_button.click()

    assert dialog.result() == dialog.DialogCode.Accepted


def test_controller_renders_every_scene_in_position_order(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(3)
    window = make_window(qtbot)
    select_story(window, story_id)

    call_count = {"n": 0}

    def _stream(config, messages) -> Iterator[RenderEvent]:
        call_count["n"] += 1
        text = f"Rendered {call_count['n']}."
        yield RenderContentDelta(text)
        yield RenderComplete(text)

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    with session_scope() as session:
        for index, scene_id in enumerate(scene_ids, start=1):
            renderings = list_renderings(session, scene_id)
            assert len(renderings) == 1
            assert renderings[0].body == f"Rendered {index}."
            assert renderings[0].is_active


def test_controller_switches_entity_column_to_scenes_tab(qtbot, monkeypatch):
    story_id, _scene_ids = seed_story_with_scenes(1)
    window = make_window(qtbot)
    select_story(window, story_id)
    window.entity_column.tabs.setCurrentIndex(0)
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream("Rendered."))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    current_tab = window.entity_column.tabs
    assert current_tab.tabText(current_tab.currentIndex()) == "Scenes"


def test_controller_stops_after_mid_run_cancel(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(3)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    gate = threading.Event()
    call_count = {"n": 0}

    def _stream(config, messages) -> Iterator[RenderEvent]:
        call_count["n"] += 1
        if call_count["n"] == 2:
            yield RenderContentDelta("Partial ")
            gate.wait(timeout=2)
            yield RenderContentDelta("more.")
            yield RenderComplete("Partial more.")
        else:
            text = f"Rendered {call_count['n']}."
            yield RenderContentDelta(text)
            yield RenderComplete(text)

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)

    controller = FullStoryRenderController(window)
    controller.start(story_id)

    qtbot.waitUntil(lambda: window.rendering_column.body_view.toPlainText() == "Partial ", timeout=2000)
    with qtbot.waitSignal(controller.finished, timeout=2000):
        window.rendering_column.cancel_button.click()
        gate.set()

    with session_scope() as session:
        assert list_renderings(session, scene_ids[0])[0].body == "Rendered 1."
        assert list_renderings(session, scene_ids[1])[0].body == "Partial "
        assert list_renderings(session, scene_ids[2]) == []


def test_controller_stops_after_mid_run_error(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(3)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    call_count = {"n": 0}

    def _stream(config, messages) -> Iterator[RenderEvent]:
        call_count["n"] += 1
        if call_count["n"] == 2:
            yield RenderContentDelta("Oops ")
            raise ConnectionError("boom")
        text = f"Rendered {call_count['n']}."
        yield RenderContentDelta(text)
        yield RenderComplete(text)

    monkeypatch.setattr(rendering_column_module, "stream_render", _stream)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    with session_scope() as session:
        assert list_renderings(session, scene_ids[0])[0].body == "Rendered 1."
        assert list_renderings(session, scene_ids[1])[0].body == "Oops "
        assert list_renderings(session, scene_ids[2]) == []


def test_controller_stops_if_story_changes_mid_run(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(2)
    other_story_id, _other_scene_ids = seed_story_with_scenes(1)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream("Rendered."))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    def switch_story_after_first_scene() -> None:
        window.current_story_id = other_story_id

    window.rendering_column.generation_finished.connect(switch_story_after_first_scene)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    with session_scope() as session:
        assert len(list_renderings(session, scene_ids[0])) == 1
        assert list_renderings(session, scene_ids[1]) == []


def test_controller_emits_finished_exactly_once(qtbot, monkeypatch):
    story_id, _scene_ids = seed_story_with_scenes(2)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream("Rendered."))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    finished_calls = []
    controller = FullStoryRenderController(window)
    controller.finished.connect(lambda: finished_calls.append(True))

    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    assert finished_calls == [True]


def test_controller_stops_if_the_next_scene_disappears_mid_run(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(2)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream("Rendered."))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    def delete_next_scene_after_first() -> None:
        with session_scope() as session:
            delete_scene(session, scene_ids[1])
        window.entity_column.scenes.refresh(select_scene_id=scene_ids[0])

    window.rendering_column.generation_finished.connect(delete_next_scene_after_first)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    with session_scope() as session:
        assert len(list_renderings(session, scene_ids[0])) == 1


def test_controller_stops_if_generate_now_cannot_start_the_next_scene(qtbot, monkeypatch):
    story_id, scene_ids = seed_story_with_scenes(2)
    window = make_window(qtbot)
    select_story(window, story_id)
    monkeypatch.setattr(rendering_column_module, "stream_render", _fake_stream("Rendered."))
    monkeypatch.setattr(rendering_column_module, "stream_accept_scene", _fake_accept_scene)

    def disable_rendering_after_first_scene() -> None:
        window.rendering_column._llm_config = None

    window.rendering_column.generation_finished.connect(disable_rendering_after_first_scene)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=5000):
        controller.start(story_id)

    with session_scope() as session:
        assert len(list_renderings(session, scene_ids[0])) == 1
        assert list_renderings(session, scene_ids[1]) == []


def test_controller_finishes_immediately_for_a_story_with_no_scenes(qtbot):
    story_id, _scene_ids = seed_story_with_scenes(0)
    window = make_window(qtbot)
    select_story(window, story_id)

    controller = FullStoryRenderController(window)
    with qtbot.waitSignal(controller.finished, timeout=2000):
        controller.start(story_id)

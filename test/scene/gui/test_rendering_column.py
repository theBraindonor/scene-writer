import pytest

import scene.data.database as database_module
from scene.core.rendering import create_rendering, set_active_rendering
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import session_scope
from scene.gui.rendering_column import NO_RENDERINGS_TEXT, NO_SCENE_SELECTED_TEXT, RenderingColumn


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def seed_scene():
    with session_scope() as session:
        story = create_story(session, title="A Story", scenario="A scenario")
        scene = create_scene(session, story_id=story.id, position=0, description="Opening")
        return scene.id


def test_shows_no_selection_message_by_default(qtbot):
    widget = RenderingColumn()
    qtbot.addWidget(widget)

    assert widget.stack.currentWidget() is widget.no_selection_label
    assert widget.no_selection_label.text() == NO_SCENE_SELECTED_TEXT


def test_shows_no_renderings_message_for_scene_without_one(qtbot):
    scene_id = seed_scene()

    widget = RenderingColumn()
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.stack.currentWidget() is widget.no_renderings_label
    assert widget.no_renderings_label.text() == NO_RENDERINGS_TEXT


def test_shows_active_rendering_body(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        rendering = create_rendering(session, scene_id=scene_id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    widget = RenderingColumn()
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)

    assert widget.stack.currentWidget() is widget.body_view
    assert widget.body_view.toPlainText() == "Once upon a time."


def test_set_scene_none_shows_no_selection_message(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        rendering = create_rendering(session, scene_id=scene_id, body="Once upon a time.")
        set_active_rendering(session, rendering.id)

    widget = RenderingColumn()
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    widget.set_scene(None)

    assert widget.stack.currentWidget() is widget.no_selection_label


def test_switching_active_rendering_and_reselecting_shows_new_body(qtbot):
    scene_id = seed_scene()
    with session_scope() as session:
        first = create_rendering(session, scene_id=scene_id, body="First version.")
        set_active_rendering(session, first.id)

    widget = RenderingColumn()
    qtbot.addWidget(widget)
    widget.set_scene(scene_id)
    assert widget.body_view.toPlainText() == "First version."

    with session_scope() as session:
        second = create_rendering(session, scene_id=scene_id, body="Second version.")
        set_active_rendering(session, second.id)

    widget.set_scene(scene_id)
    assert widget.body_view.toPlainText() == "Second version."

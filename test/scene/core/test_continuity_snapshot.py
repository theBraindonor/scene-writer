import pytest

from scene.core.continuity_snapshot import (
    create_snapshot,
    delete_snapshot,
    get_preceding_snapshot,
    get_snapshot,
    invalidate_snapshots_from,
)
from scene.core.scene import create_scene
from scene.core.story import create_story
from scene.data.database import get_engine, get_session_factory, init_db


@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    try:
        with get_session_factory(engine)() as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def story_id(session):
    story = create_story(session, title="Title", story_brief="Story brief")
    return story.id


def _make_scenes(session, story_id, count):
    return [create_scene(session, story_id=story_id, position=position, brief=f"Scene {position}").id for position in range(count)]


def test_create_and_get_snapshot(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]

    snapshot = create_snapshot(session, story_id, scene_id, "Mara is at the station.")

    assert snapshot.id is not None
    fetched = get_snapshot(session, story_id, scene_id)
    assert fetched is not None
    assert fetched.narrative_state == "Mara is at the station."
    assert fetched.narrative_state_reasoning is None


def test_create_snapshot_with_reasoning(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]

    snapshot = create_snapshot(
        session,
        story_id,
        scene_id,
        "Mara is at the station.",
        narrative_state_reasoning="Considered Mara's prior location.",
    )

    assert snapshot.narrative_state_reasoning == "Considered Mara's prior location."


def test_get_snapshot_returns_none_when_missing(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]

    assert get_snapshot(session, story_id, scene_id) is None


def test_create_snapshot_for_missing_scene_raises(session, story_id):
    with pytest.raises(ValueError, match="Scene 999 not found"):
        create_snapshot(session, story_id, 999, "State")


def test_create_snapshot_for_cross_story_scene_raises(session, story_id):
    other_story_id = create_story(session, title="Other", story_brief="Other brief").id
    other_scene_id = _make_scenes(session, other_story_id, 1)[0]

    with pytest.raises(ValueError, match="does not belong to story"):
        create_snapshot(session, story_id, other_scene_id, "State")


def test_create_duplicate_snapshot_raises(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]
    create_snapshot(session, story_id, scene_id, "First state")

    with pytest.raises(ValueError, match="already exists"):
        create_snapshot(session, story_id, scene_id, "Second state")


def test_get_preceding_snapshot_returns_none_for_first_scene(session, story_id):
    first_id, _second_id = _make_scenes(session, story_id, 2)

    assert get_preceding_snapshot(session, story_id, first_id) is None


def test_get_preceding_snapshot_returns_immediately_preceding_scene(session, story_id):
    first_id, second_id = _make_scenes(session, story_id, 2)
    create_snapshot(session, story_id, first_id, "First state")

    preceding = get_preceding_snapshot(session, story_id, second_id)

    assert preceding is not None
    assert preceding.through_scene_id == first_id


def test_get_preceding_snapshot_walks_backward_past_scene_with_no_snapshot(session, story_id):
    first_id, _second_id, third_id = _make_scenes(session, story_id, 3)
    create_snapshot(session, story_id, first_id, "First state")

    preceding = get_preceding_snapshot(session, story_id, third_id)

    assert preceding is not None
    assert preceding.through_scene_id == first_id


def test_get_preceding_snapshot_returns_none_when_no_prior_snapshot_exists(session, story_id):
    _first_id, second_id = _make_scenes(session, story_id, 2)

    assert get_preceding_snapshot(session, story_id, second_id) is None


def test_get_preceding_snapshot_returns_none_for_unknown_scene(session, story_id):
    assert get_preceding_snapshot(session, story_id, 999) is None


def test_invalidate_snapshots_from_deletes_matching_scenes_and_returns_count(session, story_id):
    first_id, second_id, third_id = _make_scenes(session, story_id, 3)
    create_snapshot(session, story_id, first_id, "First state")
    create_snapshot(session, story_id, second_id, "Second state")
    create_snapshot(session, story_id, third_id, "Third state")

    deleted = invalidate_snapshots_from(session, story_id, from_position=1)

    assert deleted == 2
    assert get_snapshot(session, story_id, first_id) is not None
    assert get_snapshot(session, story_id, second_id) is None
    assert get_snapshot(session, story_id, third_id) is None


def test_invalidate_snapshots_from_returns_zero_when_nothing_matches(session, story_id):
    first_id = _make_scenes(session, story_id, 1)[0]
    create_snapshot(session, story_id, first_id, "First state")

    deleted = invalidate_snapshots_from(session, story_id, from_position=5)

    assert deleted == 0
    assert get_snapshot(session, story_id, first_id) is not None


def test_delete_snapshot(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]
    create_snapshot(session, story_id, scene_id, "State")

    deleted = delete_snapshot(session, story_id, scene_id)

    assert deleted is True
    assert get_snapshot(session, story_id, scene_id) is None


def test_delete_missing_snapshot_returns_false(session, story_id):
    scene_id = _make_scenes(session, story_id, 1)[0]

    assert delete_snapshot(session, story_id, scene_id) is False

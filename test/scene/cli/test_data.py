import pytest
from typer.testing import CliRunner

import scene.data.database as database_module
from scene.cli.data import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database_module, "DEFAULT_DATABASE_PATH", tmp_path / "test.db")


def test_create_and_list_story():
    result = runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    assert result.exit_code == 0
    assert "Created story 1" in result.stdout

    result = runner.invoke(app, ["story", "list"])
    assert result.exit_code == 0
    assert "My Story" in result.stdout


def test_get_story():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])

    result = runner.invoke(app, ["story", "get", "1"])

    assert result.exit_code == 0
    assert "title: My Story" in result.stdout


def test_get_missing_story():
    result = runner.invoke(app, ["story", "get", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_update_story():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])

    result = runner.invoke(app, ["story", "update", "1", "--title", "New Title"])

    assert result.exit_code == 0
    assert "New Title" in result.stdout


def test_update_missing_story():
    result = runner.invoke(app, ["story", "update", "999", "--title", "New Title"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_archive_missing_story():
    result = runner.invoke(app, ["story", "archive", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_unarchive_missing_story():
    result = runner.invoke(app, ["story", "unarchive", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_archive_and_unarchive_story():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])

    result = runner.invoke(app, ["story", "archive", "1"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["story", "list"])
    assert "My Story" not in result.stdout

    result = runner.invoke(app, ["story", "unarchive", "1"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["story", "list"])
    assert "My Story" in result.stdout


def test_create_and_list_scene():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])

    result = runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives.", "--heading", "Arrival"])
    assert result.exit_code == 0
    assert "Created scene 1" in result.stdout

    result = runner.invoke(app, ["scene", "list", "1"])
    assert result.exit_code == 0
    assert "Arrival" in result.stdout


def test_get_scene():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])

    result = runner.invoke(app, ["scene", "get", "1"])

    assert result.exit_code == 0
    assert "description: The hero arrives." in result.stdout


def test_get_missing_scene():
    result = runner.invoke(app, ["scene", "get", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_update_scene():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])

    result = runner.invoke(app, ["scene", "update", "1", "--description", "The hero departs."])

    assert result.exit_code == 0
    result = runner.invoke(app, ["scene", "get", "1"])
    assert "description: The hero departs." in result.stdout


def test_update_missing_scene():
    result = runner.invoke(app, ["scene", "update", "999", "--description", "New"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_delete_scene():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])

    result = runner.invoke(app, ["scene", "delete", "1"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["scene", "get", "1"])
    assert result.exit_code == 1


def test_delete_missing_scene():
    result = runner.invoke(app, ["scene", "delete", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_create_and_list_rendering():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])

    result = runner.invoke(app, ["rendering", "create", "1", "It was a dark and stormy night."])
    assert result.exit_code == 0
    assert "Created rendering 1" in result.stdout

    result = runner.invoke(app, ["rendering", "list", "1"])
    assert result.exit_code == 0
    assert "1\tFalse" in result.stdout


def test_get_rendering():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])
    runner.invoke(app, ["rendering", "create", "1", "It was a dark and stormy night."])

    result = runner.invoke(app, ["rendering", "get", "1"])

    assert result.exit_code == 0
    assert "body: It was a dark and stormy night." in result.stdout


def test_get_missing_rendering():
    result = runner.invoke(app, ["rendering", "get", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_set_active_rendering():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])
    runner.invoke(app, ["rendering", "create", "1", "First draft."])
    runner.invoke(app, ["rendering", "create", "1", "Second draft."])

    result = runner.invoke(app, ["rendering", "set-active", "2"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["rendering", "list", "1"])
    assert "1\tFalse" in result.stdout
    assert "2\tTrue" in result.stdout


def test_set_active_missing_rendering():
    result = runner.invoke(app, ["rendering", "set-active", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_delete_rendering():
    runner.invoke(app, ["story", "create", "My Story", "A scenario"])
    runner.invoke(app, ["scene", "create", "1", "0", "The hero arrives."])
    runner.invoke(app, ["rendering", "create", "1", "First draft."])

    result = runner.invoke(app, ["rendering", "delete", "1"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["rendering", "get", "1"])
    assert result.exit_code == 1


def test_delete_missing_rendering():
    result = runner.invoke(app, ["rendering", "delete", "999"])

    assert result.exit_code == 1
    assert "not found" in result.stdout

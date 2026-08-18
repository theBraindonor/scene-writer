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

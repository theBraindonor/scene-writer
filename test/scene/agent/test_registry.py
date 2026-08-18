import pytest

from scene.agent.registry import ModelProfile, load_registry


def write_registry(tmp_path, content):
    path = tmp_path / "models.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_registry_resolves_profile_with_all_fields(tmp_path):
    path = write_registry(
        tmp_path,
        """
        profiles:
          openrouter-instruct:
            model: openrouter/anthropic/claude-3.5-sonnet
            api_base: https://openrouter.ai/api/v1
            api_key_env: OPENROUTER_API_KEY
        """,
    )

    profiles = load_registry(path)

    assert profiles == {
        "openrouter-instruct": ModelProfile(
            model="openrouter/anthropic/claude-3.5-sonnet",
            api_base="https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
        )
    }


def test_load_registry_resolves_profile_without_optional_fields(tmp_path):
    path = write_registry(
        tmp_path,
        """
        profiles:
          lmstudio-instruct:
            model: openai/my-model
        """,
    )

    profiles = load_registry(path)

    assert profiles == {"lmstudio-instruct": ModelProfile(model="openai/my-model")}


def test_load_registry_missing_file_raises(tmp_path):
    with pytest.raises(RuntimeError, match="not found"):
        load_registry(tmp_path / "does-not-exist.yaml")


def test_load_registry_without_profiles_mapping_raises(tmp_path):
    path = write_registry(tmp_path, "not_profiles: {}\n")

    with pytest.raises(TypeError, match="malformed"):
        load_registry(path)


def test_load_registry_profile_missing_model_raises(tmp_path):
    path = write_registry(
        tmp_path,
        """
        profiles:
          broken:
            api_base: http://localhost:1234/v1
        """,
    )

    with pytest.raises(RuntimeError, match="broken"):
        load_registry(path)

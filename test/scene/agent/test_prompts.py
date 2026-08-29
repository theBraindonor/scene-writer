import pytest

from scene.agent.prompts import PromptSet, load_prompts


def write_prompts(tmp_path, content):
    path = tmp_path / "agent-prompts.yaml"
    path.write_text(content, encoding="utf-8")
    return path


RENDERING_SECTION = """
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements:
            - Rule one.
            - Rule two.
          scene_brief_caption: Caption text.
          closing_instructions: Closing text.
"""


def test_load_prompts_resolves_all_fields(tmp_path):
    path = write_prompts(
        tmp_path,
        f"""
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        {RENDERING_SECTION}
        """,
    )

    prompts = load_prompts(path)

    assert prompts == PromptSet(
        coordinator_system_prompt="Coordinator prompt.",
        continuity_editor_system_prompt="Continuity prompt.",
        rendering_fiction_prefix="Prefix text.",
        rendering_scene_generation_instructions="Suffix text.",
        rendering_requirements=("Rule one.", "Rule two."),
        rendering_scene_brief_caption="Caption text.",
        rendering_closing_instructions="Closing text.",
    )


def test_load_prompts_missing_file_raises(tmp_path):
    with pytest.raises(RuntimeError, match="not found"):
        load_prompts(tmp_path / "does-not-exist.yaml")


def test_load_prompts_without_top_level_mapping_raises(tmp_path):
    path = write_prompts(tmp_path, "- not\n- a\n- mapping\n")

    with pytest.raises(TypeError, match="malformed"):
        load_prompts(path)


def test_load_prompts_missing_section_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        """,
    )

    with pytest.raises(TypeError, match="rendering"):
        load_prompts(path)


def test_load_prompts_missing_field_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        f"""
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor: {{}}
        {RENDERING_SECTION}
        """,
    )

    with pytest.raises(RuntimeError, match="continuity_editor.system_prompt"):
        load_prompts(path)


def test_load_prompts_empty_field_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        f"""
        coordinator:
          system_prompt: "   "
        continuity_editor:
          system_prompt: Continuity prompt.
        {RENDERING_SECTION}
        """,
    )

    with pytest.raises(RuntimeError, match="coordinator.system_prompt"):
        load_prompts(path)


def test_load_prompts_missing_requirements_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          scene_brief_caption: Caption text.
          closing_instructions: Closing text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.requirements"):
        load_prompts(path)


def test_load_prompts_empty_requirements_list_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements: []
          scene_brief_caption: Caption text.
          closing_instructions: Closing text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.requirements"):
        load_prompts(path)


def test_load_prompts_requirements_not_a_list_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements: Not a list.
          scene_brief_caption: Caption text.
          closing_instructions: Closing text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.requirements"):
        load_prompts(path)


def test_load_prompts_requirements_with_blank_item_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements:
            - Rule one.
            - "   "
          scene_brief_caption: Caption text.
          closing_instructions: Closing text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.requirements"):
        load_prompts(path)


def test_load_prompts_missing_scene_brief_caption_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements:
            - Rule one.
          closing_instructions: Closing text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.scene_brief_caption"):
        load_prompts(path)


def test_load_prompts_missing_closing_instructions_raises(tmp_path):
    path = write_prompts(
        tmp_path,
        """
        coordinator:
          system_prompt: Coordinator prompt.
        continuity_editor:
          system_prompt: Continuity prompt.
        rendering:
          fiction_prefix: Prefix text.
          scene_generation_instructions: Suffix text.
          requirements:
            - Rule one.
          scene_brief_caption: Caption text.
        """,
    )

    with pytest.raises(RuntimeError, match="rendering.closing_instructions"):
        load_prompts(path)

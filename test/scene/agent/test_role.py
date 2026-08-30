from scene.agent.role import AgentRole


def test_coordinating_env_var():
    assert AgentRole.COORDINATING.env_var == "SCENE_COORDINATING_AGENT"


def test_application_env_var():
    assert AgentRole.APPLICATION.env_var == "SCENE_APPLICATION_AGENT"


def test_rendering_env_var():
    assert AgentRole.RENDERING.env_var == "SCENE_RENDERING_AGENT"


def test_continuity_editing_env_var():
    assert AgentRole.CONTINUITY_EDITING.env_var == "SCENE_CONTINUITY_AGENT"

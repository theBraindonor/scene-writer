from scene.agent.role import AgentRole


def test_coordinating_env_var():
    assert AgentRole.COORDINATING.env_var == "SCENE_COORDINATING_AGENT"


def test_rendering_env_var():
    assert AgentRole.RENDERING.env_var == "SCENE_RENDERING_AGENT"

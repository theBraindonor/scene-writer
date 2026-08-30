from enum import Enum


class AgentRole(Enum):
    COORDINATING = "SCENE_COORDINATING_AGENT"
    APPLICATION = "SCENE_APPLICATION_AGENT"
    RENDERING = "SCENE_RENDERING_AGENT"
    CONTINUITY_EDITING = "SCENE_CONTINUITY_AGENT"

    @property
    def env_var(self) -> str:
        return self.value

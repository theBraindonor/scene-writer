from enum import Enum


class AgentRole(Enum):
    COORDINATING = "SCENE_COORDINATING_AGENT"
    RENDERING = "SCENE_RENDERING_AGENT"

    @property
    def env_var(self) -> str:
        return self.value

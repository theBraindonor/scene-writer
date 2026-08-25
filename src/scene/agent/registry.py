from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "models.yaml"


@dataclass(frozen=True)
class ModelProfile:
    model: str
    api_base: str | None = None
    api_key_env: str | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None


def load_registry(registry_path: Path | None = None) -> dict[str, ModelProfile]:
    path = registry_path or DEFAULT_REGISTRY_PATH
    if not path.is_file():
        raise RuntimeError(
            f"Model registry not found at {path}. Copy models.example.yaml to models.yaml and fill in your profiles."
        )

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), dict):
        raise TypeError(f"{path} is malformed: expected a top-level 'profiles' mapping.")

    profiles: dict[str, ModelProfile] = {}
    for name, fields in raw["profiles"].items():
        if not isinstance(fields, dict) or "model" not in fields:
            raise RuntimeError(f"{path}: profile {name!r} is missing its required 'model' field.")
        profiles[name] = ModelProfile(
            model=fields["model"],
            api_base=fields.get("api_base"),
            api_key_env=fields.get("api_key_env"),
            max_tokens=fields.get("max_tokens"),
            reasoning_effort=fields.get("reasoning_effort"),
        )

    return profiles

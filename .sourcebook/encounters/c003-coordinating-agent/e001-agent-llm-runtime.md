---
archived: false
campaign: c003-coordinating-agent
created_by: John Hoff
created_on: '2026-08-18T15:02:38Z'
depends_on: []
kind: scripted
name: e001-agent-llm-runtime
regions:
- agent
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T15:42:55Z'
---

# E001 — Agent LLM Runtime

## Requirements
- Add `litellm` and `python-dotenv` as runtime dependencies of the project (`[project.dependencies]` in `pyproject.toml`). `pyyaml` is already available transitively via `litellm`; do not add it explicitly unless resolution proves otherwise.
- Add a `scene.agent` module that loads and parses the model registry file (`models.yaml` at the project root, resolved the same way `scene.data.database` resolves its default database path, with an override hook for tests) into named profiles, each with a required `model` string, an optional `api_base`, and an optional `api_key_env`. Raise a clear error if the file is missing, unreadable, or malformed (not a mapping of profile name to fields, or missing the required `model` field on some profile).
- Add an `AgentRole` enumeration (`COORDINATING`, `RENDERING`) mapping each role to its role-selector environment variable name (`SCENE_COORDINATING_AGENT`, `SCENE_RENDERING_AGENT`). `RENDERING` is defined now, for consistency and to reserve the seam, even though nothing in this campaign resolves it yet.
- Add a configuration module in `scene.agent` that first loads `.env` (via `python-dotenv`'s `load_dotenv()`, a no-op if the file is absent), then, given an `AgentRole`, resolves that role's registry profile: read the role's environment variable (required — raise a clear error if unset), look up the named profile in the registry (raise a clear error naming the missing profile if not found), and resolve `api_key_env` (if present) to its value from the environment. Return a small immutable config object (`model`, `api_base`, `api_key`).
- Add a thin completion wrapper module in `scene.agent` that calls `litellm.completion()` given a resolved config object plus a list of chat messages and an optional list of tool schemas, and returns `litellm`'s response object (or an equivalent minimal representation) so callers can inspect assistant text and/or tool calls. This module must not itself know about roles, `.env`, or the registry — it only consumes an already-resolved config.
- `.env.example` (role selectors `SCENE_COORDINATING_AGENT`/`SCENE_RENDERING_AGENT` plus example `api_key_env` secrets), `models.example.yaml` (example profiles, one OpenRouter-style and one LM-Studio-style), and `.gitignore` entries for `.env`/`models.yaml` already exist as pre-work ahead of this encounter — verify they still match whatever field/env-var names this encounter ships, and update the `.example` files if anything changed during implementation.
- Cover the registry loader and the config resolution with unit tests using temporary registry files and monkeypatched environment variables (not the developer's real `.env`/`models.yaml`), covering at least: a valid profile resolves correctly with and without `api_base`/`api_key_env`; a missing role env var raises; a role env var naming a profile absent from the registry raises; a malformed registry file raises. Cover the completion wrapper with a test mocking `litellm.completion`, confirming it never touches `.env`/the registry itself.

## Rationale
This is the first encounter of `c003-coordinating-agent` and establishes the shared LLM-calling
infrastructure that the coordinator (and later the rendering agent) will build on. The
coordinating agent and the future rendering agent are highly likely to run on different models
(an "instruct" model suits tool-calling coordination; a "role-play" model suits prose
rendering), and the developer wants to swap either independently via config, with a seam a later
GUI can also flip live — so this is a named model *registry* (`models.yaml`) with per-role
*selector* environment variables pointing into it, not a single flat set of model/api_base/key
variables. Per the campaign's design decisions, the LiteLLM Python SDK is used in-process (no
proxy server), and nothing about a specific model, provider, or API key is hardcoded — it all
comes from the registry plus `.env`.

## Plan
1. Add `litellm` and `python-dotenv` to `[project] dependencies` in `pyproject.toml` and update `pdm.lock` via `pdm install -G dev`.
2. In `scene.agent`, add a `registry.py` (or similarly named) module that locates `models.yaml` at the project root (mirroring `scene.data.database`'s path-resolution pattern, with a way to override the path for tests), parses it with `yaml.safe_load`, and exposes a function returning a mapping of profile name to a small dataclass (`model`, `api_base | None`, `api_key_env | None`), raising clear errors for a missing file, non-mapping content, or a profile missing `model`.
3. In `scene.agent`, add an `AgentRole` enum (`COORDINATING`, `RENDERING`) with a property or mapping to its role-selector env var name.
4. In `scene.agent`, add a `config.py` module exposing `get_llm_config(role: AgentRole)` that calls `load_dotenv()`, reads the role's env var (raising if unset), looks up that profile name in the registry (raising if absent), resolves `api_key_env` to its environment value if set, and returns an immutable config object (`model`, `api_base`, `api_key`).
5. In `scene.agent`, add an `llm.py` module exposing `complete(config, messages, tools=None)` that calls `litellm.completion(model=config.model, api_base=config.api_base, api_key=config.api_key, messages=messages, tools=tools)`, omitting `api_base`/`api_key` from the call when not set, and returns the raw `litellm` response.
6. Confirm `.env.example`/`models.example.yaml`/`.gitignore` still reflect the exact field and env var names shipped here; adjust the `.example` files if they diverged during implementation.
7. Add unit tests under `test/scene/agent/test_registry.py`, `test/scene/agent/test_config.py`, and `test/scene/agent/test_llm.py`, using temporary registry files and monkeypatched environment variables (and a no-op/monkeypatched `load_dotenv` so tests are hermetic regardless of the developer's real `.env`), covering the scenarios in Requirements.
8. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green, HTML coverage report generated as configured.
- `pdm run lint` reports zero errors.
- Manually fill in a real profile in the local `models.yaml` (e.g. an LM Studio profile pointing at `http://localhost:1234/v1`) and set `SCENE_COORDINATING_AGENT` to its name in the local `.env`, then confirm (e.g. in a Python shell) that `get_llm_config(AgentRole.COORDINATING)` resolves the expected model/api_base without exporting shell variables.
- Manually confirm that an unset `SCENE_COORDINATING_AGENT`, and a `SCENE_COORDINATING_AGENT` naming a profile that doesn't exist in `models.yaml`, both raise clear errors.

## Log

### Review - 2026-08-18T15:20:11Z - John Hoff

Reviewed against the two applicable world-assigned lore items (linting, unit-testing) plus the `agent` region's scope — both are explicitly and correctly addressed: the Plan runs `pdm run lint` with zero-errors required at Verification, and adds `test/scene/agent/test_registry.py`, `test/scene/agent/test_config.py`, and `test/scene/agent/test_llm.py` mirroring the planned `src/scene/agent` modules, with `pdm run pytest` (HTML coverage) required green at Verification. Pre-work files (`models.yaml`, `models.example.yaml`, `.env`, `.env.example`, `.gitignore`) were checked and accurately reflect the field/env-var names the encounter plans to ship. One minor note: the new `AgentRole` enum isn't named in an explicit test scenario, though it's likely exercised incidentally via the `config.py` tests — worth confirming coverage lands on it. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T15:42:55Z - John Hoff

Verified: pdm run pytest passes 140/140 with 100% coverage across the new src/scene/agent/registry.py (model registry loader), role.py (AgentRole enum), config.py (get_llm_config), and llm.py (role-agnostic complete() wrapper); pdm run lint reports zero errors. Manually confirmed all three runtime scenarios against the real .env/models.yaml: happy-path resolution of the lmstudio-instruct profile, a clear RuntimeError when SCENE_COORDINATING_AGENT is unset, and a clear RuntimeError when it names a profile absent from models.yaml. One deviation from Plan: ruff's TRY004 required the malformed-registry-structure check to raise TypeError instead of RuntimeError; file-not-found and missing-model-field still raise RuntimeError. litellm and python-dotenv added as runtime dependencies; models.example.yaml/.env.example confirmed to match the shipped field/env-var names.

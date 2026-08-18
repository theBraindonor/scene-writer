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
status: draft
updated_by: John Hoff
updated_on: '2026-08-18T15:03:38Z'
---

# E001 — Agent LLM Runtime

## Requirements
- Add `litellm` as a runtime dependency of the project (`[project.dependencies]` in `pyproject.toml`).
- Add a configuration module in `scene.agent` that resolves, from environment variables: a required model name, an optional `api_base` (for a local LM Studio-style OpenAI-compatible endpoint), and an optional API key. Raise a clear, actionable error if the model name is not configured.
- Add a thin completion wrapper module in `scene.agent` that calls `litellm.completion()` using the resolved configuration, accepting a list of chat messages and an optional list of tool schemas, and returning `litellm`'s response object (or an equivalent minimal representation) so callers can inspect assistant text and/or tool calls.
- Do not hardcode a default model, provider, or API key anywhere — every value must come from configuration so the same code can target OpenRouter or a local LM Studio server without a code change.
- Cover the configuration resolution and the completion wrapper with unit tests, mocking `litellm.completion` so no real network call is made and no real API key is required to run the test suite.

## Rationale
This is the first encounter of `c003-coordinating-agent` and establishes the shared LLM-calling
infrastructure that the coordinator (and later scene-construction/scene-drafting agents) will
build on. Per the campaign's design decisions, the LiteLLM Python SDK is used in-process (no
proxy server), and model/provider selection is fully environment-driven so OpenRouter and a
local LM Studio server are both reachable through the same code path.

## Plan
1. Add `litellm` to `[project] dependencies` in `pyproject.toml` and update `pdm.lock` via `pdm install -G dev`.
2. In `scene.agent`, add a `config.py` module exposing a function (e.g. `get_llm_config()`) that reads `SCENE_AGENT_MODEL` (required), `SCENE_AGENT_API_BASE` (optional), and `SCENE_AGENT_API_KEY` (optional) from the environment, returning a small dataclass, and raising a clear `RuntimeError`/`ValueError` when `SCENE_AGENT_MODEL` is unset.
3. In `scene.agent`, add an `llm.py` module exposing a `complete(messages, tools=None)` function that calls `litellm.completion(model=..., api_base=..., api_key=..., messages=messages, tools=tools)`, omitting `api_base`/`api_key` from the call when not configured, and returns the raw `litellm` response.
4. Add unit tests under `test/scene/agent/test_config.py` and `test/scene/agent/test_llm.py`, monkeypatching environment variables and `litellm.completion` respectively, covering: required model missing raises; optional values omitted vs. present; `complete()` passes through messages/tools and returns the mocked response.
5. Run `pdm run pytest` and `pdm run lint` and fix any failures.

## Verification
- `pdm run pytest` passes with all existing and new tests green, HTML coverage report generated as configured.
- `pdm run lint` reports zero errors.
- Manually confirm (e.g. in a Python shell) that omitting `SCENE_AGENT_MODEL` raises a clear error, and that setting `SCENE_AGENT_MODEL`/`SCENE_AGENT_API_BASE` picks up an OpenAI-compatible local LM Studio endpoint without code changes.

## Log

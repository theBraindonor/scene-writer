---
archived: false
campaign: c001-initial-tooling
created_by: John Hoff
created_on: '2026-08-18T02:10:38Z'
depends_on: []
kind: scripted
name: e002-ruff-lint-scaffold
regions:
- agent
- cli
- data
- gui
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T02:14:45Z'
---

# E002 — Ruff Lint Scaffold

## Requirements
- Add `ruff` as a dev dependency of the project.
- Configure `ruff` (via `pyproject.toml`) with a line length of 120 characters.
- Configure `ruff` to check both `src/` and `test/`.
- The existing codebase (the `src/scene/*` placeholder packages and `test/scene/*` tests added in `e001-pytest-coverage-scaffold`) must pass `ruff check` with zero errors under this configuration.
- Document the lint command so it's easy to invoke consistently (e.g. a `pdm run` script), mirroring how `pytest` is already runnable via `pdm run pytest`.

## Rationale
This is the second encounter of the `c001-initial-tooling` campaign, following on from `e001-pytest-coverage-scaffold`. It establishes the linting tool and line-length convention called for by the just-updated `linting` lore (`ruff`, 120-character lines), giving the project a clean, enforceable lint baseline before feature work begins.

## Plan
1. Add `ruff` to the project's dev dependency group in `pyproject.toml` (alongside `crypts-and-commits`, `pytest`, `pytest-cov`), and update `pdm.lock`.
2. Add a `[tool.ruff]` section to `pyproject.toml` setting `line-length = 120`, and ensure both `src/` and `test/` are covered (default `ruff` discovery already includes the whole project root, so no explicit `include`/`exclude` should be needed unless discovery proves otherwise).
3. Run `pdm run ruff check .` against the existing `src/` and `test/` code from `e001-pytest-coverage-scaffold` and fix any reported issues so the run is clean.
4. Add a `pdm` script (e.g. `lint = "ruff check ."`) to `pyproject.toml` so linting can be invoked with `pdm run lint`.

## Verification
- Run `pdm run ruff check .` (or the added `pdm run lint` script) from the repo root and confirm zero errors.
- Run `pdm run pytest` and confirm it still passes with no regressions from any lint-driven code changes.

## Log

### Review - 2026-08-18T02:12:33Z - John Hoff

Reviewed against the linting and unit-testing world lore: the plan correctly introduces ruff as a dev dependency, sets line-length = 120, requires a clean ruff check . across src/ and test/, and adds a pdm run lint script, fully satisfying the linting lore; it also re-verifies pdm run pytest passes post-fix, preserving the unit-testing lore's pass/coverage requirements without disturbing the existing HTML coverage report setup from e001-pytest-coverage-scaffold. One minor, non-blocking note: if lint-driven fixes end up making more than cosmetic changes to the placeholder modules, the plan doesn't explicitly call for corresponding test updates, though this is unlikely to be material given the scope of the existing placeholder code. No lore conflicts found; PASS-WITH-NOTES.

### Completed - 2026-08-18T02:14:45Z - John Hoff

Verified: pdm run lint (ruff check .) reports zero errors against the existing src/scene and test/scene code with no fixes needed, line-length=120 configured in pyproject.toml, and pdm run pytest still passes all 5 tests with 100% coverage. No plan deviations.

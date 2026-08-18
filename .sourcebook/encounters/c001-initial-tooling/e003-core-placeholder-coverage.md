---
archived: false
campaign: c001-initial-tooling
created_by: John Hoff
created_on: '2026-08-18T03:49:30Z'
depends_on: []
kind: scripted
name: e003-core-placeholder-coverage
regions:
- core
status: completed
updated_by: John Hoff
updated_on: '2026-08-18T04:01:08Z'
---

# E003 — Core Placeholder Coverage

## Requirements
- Add a minimal placeholder module to the newly created `scene.core` package (`src/scene/core/__init__.py`), matching the pattern already established for `scene.cli`, `scene.agent`, `scene.data`, and `scene.gui` in `e001-pytest-coverage-scaffold`.
- Add a mirrored unit test under `test/scene/core/test_init.py` asserting against the placeholder, following the existing `test/` layout and naming convention.
- The new module and test must be picked up by the existing `pdm run pytest` configuration with no changes to `pyproject.toml`, and must pass `pdm run lint` with zero errors.

## Rationale
The `scene.core` region was created after `e001-pytest-coverage-scaffold` established placeholder coverage for the other four regions, so it's the only core package still missing a placeholder module and a mirrored test. This closes that gap so every region has a real (if trivial) unit under test before `c002-initial-data-model-and-crud` begins building `scene.core`'s actual service layer, per the `unit-testing` lore.

## Plan
1. Create `src/scene/core/__init__.py` with a `PACKAGE_NAME = "scene.core"` placeholder, matching the style of the other four `__init__.py` placeholders.
2. Create `test/scene/core/test_init.py` with a passing unit test asserting `PACKAGE_NAME == "scene.core"`, matching the existing sibling test files (no `__init__.py` in the test directory, consistent with the rest of `test/scene/`).

## Verification
- Run `pdm run pytest` with no extra arguments and confirm all tests pass, including the new `test/scene/core/test_init.py`, with `src/scene/core/__init__.py` reported at 100% coverage in the HTML/terminal report.
- Run `pdm run lint` and confirm zero errors.

## Log

### Review - 2026-08-18T03:51:12Z - John Hoff

Reviewed against the two applicable lore items (linting, unit-testing): the plan's commitment to zero ruff errors and a passing, HTML-covered pytest run under test/scene/core/test_init.py mirroring src/scene/core/__init__.py is directly consistent with both lore bodies, and cross-checking pyproject.toml confirms the existing testpaths/--cov configuration will pick up the new module and test without changes as claimed; the one unverified point is the encounter's claim of parity with the scene.cli/scene.agent/scene.data/scene.gui placeholders from e001-pytest-coverage-scaffold, which falls outside this encounter's core-only region scope and was not independently checked — overall this passes review with that noted as an unverified-but-low-risk assumption.

### Completed - 2026-08-18T04:01:08Z - John Hoff

Verified: pdm run pytest passes all 6 tests (100% coverage including the new src/scene/core/__init__.py placeholder), and pdm run lint reports zero errors. No plan deviations.

# Changelog

All notable changes to Yagra are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For the canonical changelog (Japanese), see [CHANGELOG.md](https://github.com/shogo-hs/Yagra/blob/main/CHANGELOG.md) in the repository root.

## [Unreleased]

## [0.4.1] - 2026-02-17

### Added
- **WebUI Handler Type Selector**: Handler input in Node Properties panel changed to a type selector (`llm` / `structured_llm` / `streaming_llm` / `custom`)
  - Predefined types auto-fill the handler name — no manual typing required
  - `custom` type shows free-text input for user-defined handlers
  - Fully backward compatible (existing YAML load/save behavior unchanged)

### Related
- **Goal**: G-05 (Non-engineers can operate workflows in WebUI without confusion)

## [0.4.0] - 2026-02-17

### Added
- **WebUI Handler Type Forms**: Node properties panel shows handler type-specific form sections
  - Prompt Settings / Model Settings only shown for `llm`, `structured_llm`, and `streaming_llm` handlers
  - **Schema Settings** section added for `structured_llm` (edit `schema_yaml` as YAML text)
  - **Streaming Settings** section added for `streaming_llm` (`stream: false` checkbox)
  - LLM-related sections hidden for `custom` and non-LLM handlers
- **Streaming Handler**: Added `create_streaming_llm_handler()` factory function for streaming LLM responses
  - Returns `Generator[str, None, None]` — supports both incremental and buffered processing
  - Automatically adds `stream=True` (respects explicit `stream=False` in `model.kwargs`)
  - Same retry and timeout features as `create_llm_handler()` (default timeout=60s)
  - Fully backward compatible
- **Structured Output Handler**: Added `create_structured_llm_handler()` factory function for type-safe structured output using Pydantic models
  - Specify a Pydantic model as the `schema` argument to automatically parse and validate LLM responses
  - JSON output mode enabled by default (`response_format=json_object`)
  - JSON Schema automatically injected into the system prompt
  - Same retry and timeout features as `create_llm_handler()`
  - Raises `LLMHandlerCallError` on JSON parse failure or Pydantic validation failure
  - Fully backward compatible
- **Testing**: Added 40 tests total (15+16 unit tests, 3+3 integration tests for M-14–M-16)
- **Examples**: Added `examples/llm-streaming/` with a working example (YAML + prompts + run script + README)
- **Examples**: Added `examples/llm-structured/` with a working example (YAML + prompts + run script + README)
- **Examples**: Added `examples/llm-basic/` with a working example for the basic LLM handler

### Related
- **Goal**: G-07 (DX improvement: reduce LLM node boilerplate)
- **Milestone**: M-16 (streaming handler), M-15 (structured output handler), M-14 (basic LLM handler samples)

## [0.3.1] - 2026-02-17

### Changed
- **Docstring Internationalization**: Translated all Python docstrings from Japanese to English
  - Maintained Google style docstring format
  - Ensured consistency with type hints and implementation
  - Improved Sphinx documentation accessibility for English-speaking users
  - Enhanced API documentation for international user base

## [0.3.0] - 2026-02-17

### Added
- **LLM Handler Utilities**: Added `create_llm_handler()` factory function to reduce LLM node boilerplate
  - Support for 100+ LLM providers via litellm (OpenAI, Anthropic, Google, Azure, etc.)
  - Prompt variable interpolation (`{variable}` syntax)
  - Automatic retry and timeout handling
  - Provided as extras dependency (`pip install 'yagra[llm]'` or `uv add --optional llm yagra`)
  - Fully backward compatible (no impact on existing code)
- **Testing**: Added 7 core tests (all 91 existing tests passing)
- **New Module**: `src/yagra/handlers/`
- **Dependencies**: `litellm>=1.57.10` (extras dependency)

### Changed
- Type safety: mypy strict mode compliance
- Code quality: ruff format and lint compliance

### Known Issues
- Issue #11: 6 exception tests temporarily skipped (core functionality works normally)

### Related
- **PR**: #10
- **Goal**: G-07 (DX improvement: reduce LLM node boilerplate)
- **Milestone**: M-14

## [0.2.0] - 2026-02-17

### Added
- Comprehensive English documentation for README and Sphinx (11 pages: Getting Started, User Guide, CLI Reference, Examples, etc.)
- CONTRIBUTING.md for development guidelines
- Multilingual documentation support via Sphinx i18n (English primary, Japanese secondary)
- POT/PO file generation and Japanese translation environment

### Changed
- Switched README.md from Japanese to English as the primary language
- Optimized documentation structure (README = landing page, Sphinx = detailed docs)
- Aligned with Pydantic/Click best practices

## [0.1.9] - 2026-02-16

### Fixed
- Fixed `prompt_ref` resolution failure when `bundle_root` was not specified in library usage; now searches parent directories to resolve `prompts/...` paths.

## [0.1.8] - 2026-02-16

### Changed
- Switched Studio frontend dependencies (Vue / Vue Flow) from CDN to bundled local assets, enabling offline usage.
- Changed `yagra visualize` output HTML to bundle Mermaid locally for offline rendering.

### Fixed
- Fixed Studio `prompt yaml` dropdown resetting selection unexpectedly during candidate reload; Node Properties now preserves selection state.
- Prevented race condition in `loadStudioFiles()` where stale responses could overwrite newer state.

## [0.1.7] - 2026-02-15

### Fixed
- Unified Studio `prompt_ref` path resolution to workspace root basis, fixing incorrect resolution of `prompts/...` as `workflows/prompts/...`.
- When `bundle_root` is not specified with `studio --workflow`, workspace root is now used as default, aligning save/load and runtime reference resolution.

## [0.1.6] - 2026-02-15

### Changed
- Changed Studio `prompt yaml` auto-generation target from workflow sibling directory to `prompts/` under workspace root (project root).
- Adjusted `studio --workflow` default `workspace_root` to prefer project root (current directory) when workflow is under the current directory.

## [0.1.5] - 2026-02-14

### Fixed
- Fixed JavaScript syntax error during Studio Launcher initialization that prevented `Open Existing Workflow` list from displaying.
- Added regression tests for backslash normalization logic in HTML responses.

## [0.1.4] - 2026-02-14

### Fixed
- Fixed `prompt_ref` saving workspace-relative paths instead of workflow-relative paths when editing workflows in subdirectories via Studio.
  - Save: Normalize `prompt_ref` to workflow-relative path.
  - Load: Convert workflow-relative `prompt_ref` to workspace-relative for Studio file API compatibility.

## [0.1.3] - 2026-02-14

### Added
- Added `prompt_entries` to `POST /api/studio/file/read` to reflect prompt content directly in Node Properties.
- Added `prompt key` input to Node Properties, enabling `prompt_ref=<path>#<key>` creation from the UI.

### Changed
- Fully removed `model_ref`; unified model configuration to inline `nodes[].params.model` definitions.
- Consolidated Studio prompt workflow into Node Properties; removed `Workflow Settings.prompt_catalog` and `Prompt File` sections.
- Unified `prompt_ref` resolution to path-based (`<path>` / `<path>#<key>`).
- Changed prompt YAML auto-generation target from workspace root to `prompts/` under the workflow YAML directory.

## [0.1.2] - 2026-02-14

### Added
- Added Workflow Studio launcher flow (existing workflow selection / new workflow creation).
- Added save-time backup and rollback safety for Studio initial operations.
- Added edge connection port (source/target handle) persistence.

### Changed
- Redesigned Studio Node Properties as dedicated forms for editing `system prompt` / `user prompt` and model settings.
- Organized `prompt_ref` / `model_ref` catalog reference flow and Studio API documentation.
- Updated validation to allow `edges: []` for single-node workflows.
- Improved Studio inbound port separation and quickstart/API documentation.

### Fixed
- Added runtime parameter normalization for `prompt_ref` / `model_ref` usage, unifying ref/inline input runtime representations.

## [0.1.1] - 2026-02-14

### Changed
- Renamed package and import name from `graphyml` to `yagra`; unified public API primary name to `Yagra`.
- Added tag name (`vX.Y.Z`) and `pyproject.toml` version consistency check to publish workflow.

## [0.1.0] - 2026-02-13

### Added
- Implemented Yagra YAML schema (Pydantic) and validation logic.
- Implemented Registry pattern (port + in-memory adapter).
- Implemented builder to construct LangGraph StateGraph from workflow YAML.
- Added `Yagra.from_workflow(...)` / `invoke(...)` public API.
- Added example YAMLs with branching, loops, and split references in `examples/`.
- Set up quality gates (ruff/mypy/pytest, pre-commit/pre-push).

### Changed
- Added Zero-Boilerplate usage examples and sample navigation to README.
- Updated `docs/product/*` goals, milestones, and progress.

## Links

- [PyPI](https://pypi.org/project/yagra/)
- [GitHub Repository](https://github.com/shogo-hs/Yagra)
- [GitHub Releases](https://github.com/shogo-hs/Yagra/releases)

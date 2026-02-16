# Changelog

All notable changes to Yagra are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For the complete changelog, see [CHANGELOG.md](https://github.com/shogo-hs/Yagra/blob/main/CHANGELOG.md) in the repository.

## [Unreleased]

### Added
- Comprehensive English documentation for README and Sphinx
- CONTRIBUTING.md for development guidelines
- Multilingual documentation support (English primary, Japanese secondary)

## [0.1.9] - 2026-01-XX

### Added
- Template library (`yagra init` command)
- JSON Schema export (`yagra schema` command)
- Structured validation output (`yagra validate --format json`)

### Changed
- Removed `model_ref` in favor of inline model definitions
- Improved Studio UI with enhanced visual design

## [0.1.8] - 2026-01-XX

### Added
- Studio WebUI for visual workflow editing
- Drag-and-drop node/edge management
- Diff preview and backup/rollback support

## [0.1.7] - 2026-01-XX

### Added
- `yagra visualize` command for read-only HTML generation
- Prompt reference resolution with `prompt_ref`

### Changed
- Removed inline `params.prompt` in favor of external `prompt_ref`

## [0.1.0] - 2025-XX-XX

### Added
- Initial release
- YAML-based workflow definitions
- Pydantic schema validation
- Registry pattern for handler resolution
- Conditional branching and loops

## Links

- [PyPI](https://pypi.org/project/yagra/)
- [GitHub Repository](https://github.com/shogo-hs/Yagra)
- [GitHub Releases](https://github.com/shogo-hs/Yagra/releases)

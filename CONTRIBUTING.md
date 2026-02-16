# Contributing to Yagra

Thank you for your interest in contributing to Yagra! This guide will help you get started with development.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

### Clone and Install

```bash
git clone https://github.com/shogo-hs/Yagra.git
cd Yagra
uv sync --dev
```

This will install Yagra in editable mode along with all development dependencies.

## Project Structure

```
Yagra/
├── src/
│   └── yagra/
│       ├── adapters/       # Inbound/Outbound adapters
│       ├── application/    # Use cases and services
│       ├── domain/         # Domain entities and services
│       ├── ports/          # Port interfaces
│       ├── templates/      # Workflow templates
│       └── web_assets/     # Studio UI assets
├── tests/                  # Test suite
├── examples/               # Example workflows
│   ├── workflows/
│   └── prompts/
└── docs/                   # Documentation
    ├── sphinx/
    └── product/

```

### Architecture

Yagra follows **Hexagonal Architecture** (Ports and Adapters):

- **Domain**: Core business logic, independent of external concerns
- **Application**: Use cases orchestrating domain logic
- **Ports**: Interfaces defining boundaries
- **Adapters**: Implementations connecting to external systems (inbound: CLI/API, outbound: file system, etc.)

Dependency rule: **Outer layers depend on inner layers**, never the reverse.

## Coding Standards

### Python

- **Type Hints**: Required for all function signatures
- **Docstrings**: Use Google style with Japanese descriptions
  - Include `Args`, `Returns`, and `Raises` sections
  - Explain intent, not just what the code does
- **Formatting**: Use `ruff format` (automatically applied by pre-commit)
- **Linting**: Use `ruff check` with rules: E4, E7, E9, F, I, UP, B, D
- **Type Checking**: Use `mypy` with strict configuration

### Design Principles

Follow **SOLID** principles:
- Single Responsibility
- Open/Closed
- Liskov Substitution
- Interface Segregation
- Dependency Inversion

Follow **DRY**, **KISS**, and **YAGNI**.

## Development Commands

### Quality Gates

Run all quality checks before committing:

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run mypy .

# Run tests
uv run pytest -q

# Run all checks (recommended)
uv run pre-commit run --all-files
```

### Pre-commit Hooks

Pre-commit hooks are automatically installed during `uv sync`. They run:
- `ruff format`
- `ruff check`
- `mypy`

If pre-commit checks fail, fix the issues and commit again.

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=yagra --cov-report=html

# Run specific test file
uv run pytest tests/test_yagra.py

# Run with verbose output
uv run pytest -v
```

### Documentation

#### Build Sphinx Documentation Locally

```bash
uv run sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html
```

Open `docs/sphinx/_build/html/index.html` in your browser.

#### Documentation Site

- GitHub Pages: [https://shogo-hs.github.io/Yagra/](https://shogo-hs.github.io/Yagra/)
- Auto-deployed via `.github/workflows/docs.yml` on push to `main`

### Translating Documentation

Yagra documentation supports multiple languages (English primary, Japanese secondary).

**Update translations**:

```bash
# 1. Generate POT files after modifying source
uv run sphinx-build -b gettext docs/sphinx/source docs/sphinx/source/locale

# 2. Update Japanese PO files
uv run sphinx-intl update -p docs/sphinx/source/locale -l ja -d docs/sphinx/source/locale

# 3. Edit PO files in docs/sphinx/source/locale/ja/LC_MESSAGES/*.po

# 4. Build Japanese documentation
uv run sphinx-build -b html -D language=ja docs/sphinx/source docs/sphinx/_build/html-ja
```

See `docs/sphinx/README.md` for detailed translation guidelines.

## Package Management

### Adding Dependencies

**Use `uv add`, NOT `pip install`:**

```bash
# Add runtime dependency
uv add langgraph

# Add dev dependency
uv add --group dev pytest

# Update dependencies
uv sync
```

### Package Updates

```bash
# Update all packages
uv lock --upgrade

# Sync environment
uv sync
```

## Environment Variables

- `.env.development`: Development environment variables
- `.env.production`: Production environment variables
- Use `dotenvx` for encrypted secrets with `encrypted:` prefix
- **Never commit `.env.keys`**

## Git Workflow

### Branching

- `main`: Stable branch
- `feature/xxx`: Feature branches
- `fix/xxx`: Bug fix branches

### Commit Messages

Follow conventional commits:

```
feat: add JSON schema export command
fix: resolve prompt_ref resolution issue
docs: update README with new CLI examples
refactor: simplify state graph builder
test: add tests for template initializer
```

### Pull Requests

1. Create a feature branch
2. Make changes with passing quality gates
3. Write tests for new features
4. Update documentation if needed
5. Submit PR with clear description

## Release Process

### PyPI Publishing

Releases are automated via GitHub Actions when a `v*` tag is pushed.

**Workflow:** `.github/workflows/publish.yml`
- Triggered by: `v*` tag push (e.g., `v0.2.0`)
- Build: `uv build`
- Validation: `twine check`
- Publish: PyPI via OIDC (Trusted Publisher)

**Prerequisites:**
- PyPI Trusted Publisher configured for `shogo-hs/Yagra`
- `pypi` environment available in GitHub Actions
- Version in `pyproject.toml` matches git tag

**Example Release:**

```bash
# Update version in pyproject.toml
# Update CHANGELOG.md

# Commit changes
git add pyproject.toml CHANGELOG.md
git commit -m "chore: bump version to 0.2.0"

# Create and push tag
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

GitHub Actions will automatically build and publish to PyPI.

## Documentation Guidelines

### README.md

- Keep concise (5 minutes read time)
- Focus on "what" and "why", not "how" (details go to Sphinx)
- Include badges, quick start, and links to documentation
- **English is the primary language** for README.md

### Sphinx Documentation

- **English** is the primary language
- Japanese translations are provided via Sphinx i18n
- Structure: index → getting_started → user_guide → api → examples
- Use Markdown (`.md`) with MyST parser
- Auto-generate API docs with `sphinx-autodoc`

### Docstrings

- Use Google style
- Write in **Japanese** (日本語で書く)
- Include `Args`, `Returns`, `Raises` sections
- Explain purpose and intent, not just implementation

Example:

```python
def build_state_graph(spec: GraphSpec) -> StateGraph:
    """GraphSpec から LangGraph の StateGraph を構築する。

    ノード定義、エッジ定義、条件分岐を含む完全なグラフを生成する。
    handler 名は registry で解決する必要がある。

    Args:
        spec: 検証済みの workflow 仕様。

    Returns:
        コンパイル可能な StateGraph インスタンス。

    Raises:
        ValueError: ノード ID が重複している場合。
    """
    ...
```

## Questions or Issues?

- **GitHub Issues**: [https://github.com/shogo-hs/Yagra/issues](https://github.com/shogo-hs/Yagra/issues)
- **Discussions**: [https://github.com/shogo-hs/Yagra/discussions](https://github.com/shogo-hs/Yagra/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

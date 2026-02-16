# Contributing to Yagra

Thank you for your interest in contributing to Yagra! This guide will help you get started.

For detailed development setup and guidelines, see [CONTRIBUTING.md](https://github.com/shogo-hs/Yagra/blob/main/CONTRIBUTING.md) in the repository root.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended package manager)

### Setup

```bash
git clone https://github.com/shogo-hs/Yagra.git
cd Yagra
uv sync --dev
```

### Run Quality Checks

```bash
uv run pre-commit run --all-files
```

## Project Structure

```
Yagra/
├── src/yagra/          # Source code
│   ├── adapters/       # Inbound/Outbound adapters
│   ├── application/    # Use cases and services
│   ├── domain/         # Domain entities and services
│   ├── ports/          # Port interfaces
│   └── templates/      # Workflow templates
├── tests/              # Test suite
├── examples/           # Example workflows
└── docs/               # Documentation
```

## Development Workflow

1. **Fork and Clone**: Fork the repository and clone your fork
2. **Create Branch**: `git checkout -b feature/my-feature`
3. **Make Changes**: Implement your feature or fix
4. **Run Tests**: `uv run pytest`
5. **Run Quality Checks**: `uv run pre-commit run --all-files`
6. **Commit**: Follow conventional commit format
7. **Push**: `git push origin feature/my-feature`
8. **Create PR**: Submit a pull request with clear description

## Coding Standards

- **Type Hints**: Required for all function signatures
- **Docstrings**: Use Google style with Japanese descriptions
- **Formatting**: `ruff format .`
- **Linting**: `ruff check .`
- **Type Checking**: `mypy .`

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=yagra --cov-report=html

# Run specific test file
uv run pytest tests/test_yagra.py
```

## Documentation

### Building Sphinx Documentation

```bash
uv run sphinx-build -b html docs/sphinx/source docs/sphinx/_build/html
```

Open `docs/sphinx/_build/html/index.html` in your browser.

### Documentation Guidelines

- Write in English (primary language)
- Use Markdown (`.md`) with MyST parser
- Include code examples for all features
- Update docstrings for Python API changes

## Questions?

- **GitHub Issues**: [https://github.com/shogo-hs/Yagra/issues](https://github.com/shogo-hs/Yagra/issues)
- **Discussions**: [https://github.com/shogo-hs/Yagra/discussions](https://github.com/shogo-hs/Yagra/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

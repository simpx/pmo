# AGENTS instructions for PMO

## Scope
These instructions apply to the entire repository.

## Design principles
- Aim for simplicity and clarity; avoid over-engineering.
- Prefer explicit behavior and minimal public APIs.
- This project is a development-time helper, **not** a production-ready tool.
- Optimize for developer experience and iteration speed rather than runtime performance.

## Code style
- Target Python 3.10 or later.
- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions.
- Use four spaces for indentation and double quotes for strings.
- Include type hints and docstrings for public functions and classes.

## Dependency management
- Use the [`uv`](https://github.com/astral-sh/uv) tool to manage dependencies.
- Install all dependencies (including dev extras) with:
  ```bash
  uv sync --all-extras --group dev
  ```

## Testing and build
- Run the full test suite before committing:
  ```bash
  uv run pytest
  ```
- When packaging‑related files are changed, ensure the project builds:
  ```bash
  uv build
  ```

## Documentation
- Update `README.md` or files in `docs/` when behavior or interfaces change.

## Commit guidelines
- Use descriptive commit messages that explain the change.


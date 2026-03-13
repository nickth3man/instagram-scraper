# Contributing

## Development Setup

```bash
uv sync --all-groups
uv run pre-commit install
```

## Local Checks

Run these before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
```

## Workflow

- Put application code in `src/instagram_scraper/`
- Put tests in `tests/`
- Keep generated scraper output in `data/` out of version control
- Prefer small focused pull requests

## Tooling

- Dependency management: `uv`
- Linting and formatting: `ruff`
- Type checking: `ty`
- Testing: `pytest`
- CI: GitHub Actions in `.github/workflows/ci.yml`

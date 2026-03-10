
## Development Commands

### Setup
```bash
uv sync                 # Install dependencies
```

### Running Scrapers
```bash
uv run instagram-scraper-profile --username <username>
uv run instagram-scraper-browser-dump <args>
uv run instagram-scraper-download-videos <args>
```

### Testing
```bash
# Run all tests (use python -m pytest on Windows due to uv path bug)
uv run python -m pytest

# Run specific test file
uv run python -m pytest tests/test_async_http.py

# Run with verbose output
uv run python -m pytest -v

# Run specific test
uv run python -m pytest tests/test_config.py::test_retry_config_defaults

### File Size Guardrail

Keep files between 150-500 lines:

1. Run: `uv run python -m pytest tests/test_file_size.py -v`
2. If tests fail, refactor large files into smaller modules
3. Find natural split points - don't force arbitrary divisions
4. Re-run tests until they pass

Current results: {test_output}

### Linting and Type Checking
```bash
# Lint with Ruff
uv run ruff check .

# Auto-fix Ruff issues
uv run ruff check . --fix

# Type check with Ty
uv run ty check

# Format code
uv run ruff format .
```

## Code Architecture

### Entry Points
The package provides multiple CLI entrypoints via `pyproject.toml`:
- `instagram-scraper` - Main entrypoint (cli.py)
- `instagram-scraper-profile` - Profile scraper using Instaloader
- `instagram-scraper-browser-dump` - Browser data-based scraper
- `instagram-scraper-download-videos` - Video download workflow

### Module Organization

**Core Infrastructure:**
- `config.py` - Unified configuration dataclasses (RetryConfig, HttpConfig, OutputConfig, ScraperConfig)
- `_shared_io.py` - File I/O utilities with atomic writes, file locking, and durability guarantees
- `logging_config.py` - Structured JSON logging with context binding via LogContext
- `exceptions.py` - Domain-specific exception hierarchy (InstagramError, RateLimitError, NetworkError, etc.)
- `error_codes.py` - Standardized error code enum for consistent error identification

**HTTP Clients:**
- `_async_http.py` - Async HTTP client using aiohttp with retry logic, backoff, and Instagram-specific headers
- `_instagram_http.py` - Instagram-specific HTTP utilities

**Scraper Workflows:**
- `scrape_instagram_profile.py` - Profile scraper using Instaloader (sync)
- `scrape_instagram_from_browser_dump.py` - Browser cookie-based scraper
- `async_comments.py` - Async comment fetching workflow

### Key Patterns

**Configuration:** All scrapers use the unified `ScraperConfig` dataclass which composes `HttpConfig`, `OutputConfig`, and scraper-specific settings. Configuration is frozen and uses slots for performance.

**Error Handling:** The codebase uses typed exceptions (`InstagramError` hierarchy) combined with structured error codes (`ErrorCode` enum). Network errors wrap the original exception for debugging.

**Logging:** Structured JSON logging is standard. Use `get_logger(__name__)` and `LogContext` for request-scoped fields. Logs are single-line JSON for log aggregation.

**File I/O:** All writes use atomic operations via `atomic_write_text()` and `write_json_line()`. CSV writes use `append_csv_row()` with file locking via `locked_path()` for inter-process coordination.

**Async/Sync:** The codebase supports both synchronous (Instaloader) and asynchronous (aiohttp) workflows. Async functions are prefixed with `async_` and use proper resource cleanup.

**Data Output:** Scrapers produce both JSON (instagram_dataset.json with nested data) and CSV (flat posts.csv and comments.csv) outputs. Summary metadata is written to summary.json.

## Type Checking and Linting

# Ty Guardrails

- Never relax Ty strictness. Keep `[tool.ty.rules] all = "error"` and `[tool.ty.terminal] error-on-warning = true`.
- Never add Ty rule overrides that downgrade any check to `"warn"` or `"ignore"`.
- Never enable suppression-based type checking escapes, including `# type: ignore`, `# ty: ignore`, or `@no_type_check`.
- Keep `[tool.ty.analysis] respect-type-ignore-comments = false`.

# Ruff Guardrails

- Keep production Ruff checks at maximum strictness. Do not reduce rule coverage for `src/`, do not disable preview lint rules, and do not add global `lint.ignore` or `lint.extend-ignore` settings.
- Test-only Ruff relaxations are allowed under `tests/` when they are narrowly scoped to common test ergonomics and do not weaken production code rules.
- Never add inline Ruff suppression comments such as `# noqa`, `# noqa: ...`, or file-level Ruff disables.
- Never change Ruff settings to make the codebase easier to pass. Fix the code instead.

# Completion Gate

- Keep Ty strict for production code. Test-only exclusions are allowed if they do not weaken `src/` checking.
- Before completing any task, run Ruff, Ty, and the full test suite, then keep iterating until all three pass.
- Do not claim success, completion, or readiness unless the latest `ruff check .`, `ty check`, and full test run have all passed in the current workspace state.

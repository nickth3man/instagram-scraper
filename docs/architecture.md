# Architecture Overview: instagram-scraper

This document describes the high‑level architecture, key modules, data flows, and design decisions for the instagram-scraper project. It is intended for maintainers and contributors to understand how the system is organized, how components interact, and how to extend or modify behavior with minimal risk.

## Goals and Design Principles
- Clear separation of concerns: networking, configuration, logging, error handling, and domain logic are modularized.
- Robust error handling: standardized error codes and contextual logging to ease debugging and reliability.
- Asynchronous I/O: non-blocking HTTP and parallel operations where beneficial (e.g., parallel comment fetching).
- Testability: modules are designed to be testable in isolation with deterministic behavior.
- Extensibility: adding new scrapers, parsers, or transports should require minimal changes to existing components.

## Reference Architecture

- Presentation/API (CLI/Script entry points) -- high‑level orchestration of scraping tasks.
- Application Layer -- coordinates domain logic, orchestrates modules, and applies business rules.
- Domain/Core -- domain models and error handling primitives.
- Infrastructure/Adapters -- concrete implementations for networking, I/O, and external services.

The project emphasizes a clean separation between the application logic and the infrastructure concerns so that changes to networking or logging do not force changes in business logic.

## Layered Architecture Details

1) Presentation / Entry Points
- Entry points (such as CLI scripts) initiate workflows (e.g., scrape profile, download videos).
- They interact with the application layer via well-defined function calls and return structured results.

2) Application Layer
- Orchestrates tasks, enforces workflow rules, and coordinates modules.
- Responsible for input validation, sequencing, and assembling outputs for reporting.

3) Domain / Core
- Defines domain primitives and error handling contracts.
- Centralizes error codes (see error_codes.py) and exception hierarchy (see exceptions.py).

4) Infrastructure / Adapters
- Networking: an asynchronous HTTP client abstraction (see _async_http.py) used by scraper modules to fetch data without blocking.
- Logging: structured JSON logging helper (see logging_config.py) to emit consistent logs with context.
- Configuration: centralized configuration loader (see config.py) that reads environment variables and config files.
- Async helpers: utilities for running I/O-bound tasks in parallel (see async_comments.py).

## Core Modules (new/updated in Wave 1)

- src/instagram_scraper/exceptions.py
  - Custom exception hierarchy for domain and IO errors.
- src/instagram_scraper/logging_config.py
  - Structured JSON logging with a context manager to enrich logs with request/operation metadata.
- src/instagram_scraper/error_codes.py
  - Enum-based error codes used across the codebase instead of string literals.
- src/instagram_scraper/config.py
  - Unified configuration loader with sane defaults and environment variable overrides.
- src/instagram_scraper/_async_http.py
  - Async HTTP client with timeout control, retries, and backoff strategies.
- src/instagram_scraper/async_comments.py
  - Parallel comment fetching logic enabling concurrent requests.

- Note: The repository already contains _instagram_http.py (lower-level HTTP interactions) which is consumed by the above components. The design encourages using the shared async HTTP client for all outbound requests.

## Data Flow Overview

- User/CLI triggers a scraper action (e.g., scrape profile).
- The entry point validates inputs and invokes application layer components.
- Application layer constructs a workflow and delegates to infrastructure adapters:
  - Networking: fetch HTML/JSON data via the async HTTP client.
  - Parsing/Processing: extract needed fields, handle media assets, and prepare result models.
  - Parallel tasks: for independent tasks (e.g., fetching multiple comments) use async_comments.py to perform concurrent requests.
- Results are buffered and returned to the caller with structured metadata and any required logs.

## Error Handling Strategy
- All errors are represented by standardized error codes from error_codes.py.
- Exceptions propagate with additional context to aid debugging while preserving a stable API surface.
- Logging_config.py provides structured logs with a consistent schema including correlation IDs, operation names, and timing.

## Logging Strategy
- Logging is JSON-based for easy ingestion by log pipelines.
- Each operation includes contextual fields (operation, resource_id, status, duration, error_code when applicable).
- LogContext (inside logging_config.py) helps attach metadata to logs around a given operation.

## Configuration and Secrets
- Configuration is centralized in config.py; secrets are read from environment variables and loaded via a safe defaults strategy.
- No hard-coded credentials are stored; sensitive information is provided at runtime via environment/config mechanisms.

## Testing and Validation Principles
- Unit tests target individual modules (exceptions, error_codes, config, async HTTP wrappers).
- Integration tests exercise the end-to-end orchestration paths with mocked/network-disabled I/O where possible.
- Linting and type checks are supported by Ruff and Ty in the development workflow (note: not executed in this document).

## Extensibility and Maintenance Guidance
- New scrapers or parsers should live in dedicated modules with clear interfaces.
- Use the shared HTTP client to standardize timeouts and retry logic across all outbound requests.
- Add new error codes to error_codes.py to reflect new failure modes rather than reusing generic strings.
- Extend logging with additional fields only when useful for troubleshooting and observability.

## References and Further Reading
- Current modules and their responsibilities as described in this document.
- Existing unit tests for new modules (tests/test_exceptions.py, tests/test_logging_config.py, tests/test_error_codes.py, tests/test_config.py, tests/test_async_http.py, tests/test_async_comments.py).

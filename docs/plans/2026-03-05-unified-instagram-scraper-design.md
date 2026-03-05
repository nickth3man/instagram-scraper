# Unified Instagram Scraper Design

Date: 2026-03-05

## Goal

Expand the repository from a small set of script-oriented scrapers into a single one-shot CLI that can scrape:

- a full profile by username
- a direct post or reel URL
- a list of URLs
- hashtags
- locations
- followers of a seed account
- following of a seed account
- likers discovered from seed posts
- commenters discovered from seed posts
- stories from usernames or hashtags

The expanded tool must preserve the existing ability to scrape an entire page from a username or a direct URL. It must keep a normalized output model across all modes and remain primarily HTTP-first rather than becoming a browser-first interaction bot.

## Non-Goals

- No automation of likes, follows, comments, unfollows, pods, or similar engagement behavior.
- No campaign scheduler or always-on daemon. This remains a one-shot CLI tool.
- No browser-first crawling architecture.
- No weakening of the current strict linting, typing, or verification rules.

## Product Shape

The repository will provide a unified `instagram-scraper` CLI with nested scrape subcommands while preserving the current entrypoints as compatibility wrappers.

Proposed command shape:

- `instagram-scraper scrape profile --username <name>`
- `instagram-scraper scrape url --url <post-or-reel-url>`
- `instagram-scraper scrape urls --input <file-or-tool-dump>`
- `instagram-scraper scrape hashtag --hashtag <tag>`
- `instagram-scraper scrape location --location <id-or-slug>`
- `instagram-scraper scrape followers --username <seed>`
- `instagram-scraper scrape following --username <seed>`
- `instagram-scraper scrape likers --username <seed> --posts-limit <n>`
- `instagram-scraper scrape commenters --username <seed> --posts-limit <n>`
- `instagram-scraper scrape stories --username <seed>`
- `instagram-scraper scrape stories --hashtag <tag>`

Shared flags:

- `--output-dir`
- `--limit`
- `--resume`
- `--reset-output`
- `--raw-captures`
- `--cookie-header`
- session or auth-state options
- request pacing and retry options
- filter options or a config-file path

## Core Design

The architecture is organized into four layers.

### 1. Seed Resolution

Each subcommand converts its user input into normalized targets such as usernames, post URLs, story targets, hashtags, location IDs, or user IDs. This layer is responsible for discovery and expansion only.

Examples:

- `profile --username` resolves one profile target.
- `url --url` resolves one direct media target.
- `followers --username` resolves a stream of discovered user targets.
- `likers --username` resolves seed posts first, then discovered user targets from those posts.

### 2. Fetch Providers

Providers retrieve data for normalized targets.

Primary providers:

- `instaloader` for full-profile, stories, tagged, reels, and other supported surfaces where it remains reliable
- raw HTTP for media info, comments, URL-derived lookups, paginated discovery, and normalized API consumption

Fallback provider:

- browser automation only for auth-state capture, cookie refresh, or target resolution when the primary providers fail

Provider selection is mode-specific. No single provider is assumed to support every surface reliably.

### 3. Normalization Pipeline

All providers emit the same internal record types:

- `RunSummary`
- `TargetRecord`
- `UserRecord`
- `PostRecord`
- `CommentRecord`
- `StoryRecord`
- `ErrorRecord`
- `RawCaptureRecord`

This layer is the contract boundary between extraction and storage.

### 4. Artifact Writer

Every run writes the same stable artifact family:

- `summary.json`
- `targets.ndjson`
- `users.ndjson`
- `posts.ndjson`
- `comments.ndjson`
- `stories.ndjson`
- `errors.ndjson`
- mode-specific CSV exports where useful
- optional `raw/` captures when enabled

The filesystem output remains the primary archive. Supporting metadata for dedupe and resumability may also be stored in SQLite.

## Library Decisions

The implementation will use the following libraries.

### Typer

Use `Typer` to build the unified CLI tree with nested subcommands and typed options. It is a better fit than continuing to expand `argparse`.

### Pydantic

Use `Pydantic` models for validated config, input parsing, normalized records, and JSON serialization boundaries.

### SQLAlchemy

Use `SQLAlchemy` with SQLite for lightweight local metadata state:

- run registry
- target provenance
- dedupe keys
- freshness timestamps
- provider outcomes
- optional auth/session metadata references

This database is support state, not the canonical archive of scraped content.

### HTTPX

Use `HTTPX` as the long-term raw HTTP provider abstraction, replacing or wrapping the current `requests`-based code where useful. The goals are stricter timeouts, better client ergonomics, connection pooling, and richer instrumentation hooks.

### Rich

Use `Rich` for progress bars, artifact summaries, support-tier display, and readable error output in the terminal.

### structlog

Use `structlog` for structured logging around:

- run lifecycle
- provider selection
- auth state
- request budget events
- fallback activation
- checkpoint writes
- final run metrics

### diskcache

Use `diskcache` for ephemeral, run-adjacent caching such as:

- resolved location IDs
- temporary target expansions
- repeatable page cursors
- session bootstrap helpers

This cache is optional and should not replace the SQLite metadata store.

### orjson

Use `orjson` as the JSON backend for high-volume NDJSON and summary serialization when record throughput matters.

### Explicitly Excluded

Do not use:

- `tqdm`
- `SQLModel`

`Rich` covers the terminal UX needs, and `SQLAlchemy` plus `Pydantic` keeps persistence and validation concerns separate while the schema is still evolving.

## Filtering and Selection

Filtering is inspired by InstaPy’s targeting ideas but adapted for scraping rather than engagement.

Supported filter categories:

- text filters: mandatory words, ignored words, language gates
- account filters: private/public, business/non-business, profile picture presence, bio keywords
- relationship filters: follower count, following count, post count, follower/following ratio
- media filters: photos, videos, reels, carousels, stories
- engagement filters: likes, comments, recency

Design rules:

- filters are explicit, not hidden defaults
- filtering should happen before deep expansion whenever possible
- dedupe is per run by normalized IDs
- records discovered through multiple paths are fetched once and annotated with provenance

## Support Tiers

Not all modes are equally stable. The CLI and docs should make that visible.

### Stable

- profile by username
- direct post or reel URL
- existing browser-dump URL list ingestion

### Auth-Required

- hashtags
- locations
- tagged
- reels
- stories

### Experimental

- followers
- following
- likers
- commenters

Experimental here means “supported, but expected to require more provider fallbacks and regression maintenance”.

## Authentication Strategy

Authentication is a first-class concern.

Supported mechanisms:

- cookie header input
- reusable session files
- browser cookie import
- browser auth-state capture

Rules:

- prefer reusing existing session state over repeated fresh logins
- browser automation is used to establish or refresh state, then the run returns to HTTP or Instaloader providers
- the CLI performs capability preflight and fails early if a mode requires auth and no usable auth state is available

## Rate Limits and Run Safety

The tool must assume rate limits are real and variable.

Safety controls:

- single-run request budget with per-endpoint accounting
- no parallel scraping by default
- adaptive slowdown after warning signals
- hard cooldown on repeated 429s or equivalent throttle signals
- checkpoint and exit rather than retry loops after threshold exhaustion
- resumability through persisted checkpoints and metadata state

The system must avoid assuming that it is the only consumer of Instagram resources on the machine or account.

## Browser Fallback Policy

Browser fallback exists, but it is not a primary scraper.

Allowed use cases:

- auth-state capture
- cookie import or refresh
- resolution of IDs or targets when public or API methods fail

Disallowed default behavior:

- driving full extraction through the browser for all modes
- expanding the system into a Selenium-style engagement bot

## Data Model

Normalized record families:

- `RunSummary`: high-level run metadata and file outputs
- `TargetRecord`: seed targets, discovered targets, provenance, support tier
- `UserRecord`: normalized user/account details and relationship counters
- `PostRecord`: media identity, caption, timestamps, counts, ownership, location, media type
- `CommentRecord`: normalized comment text, author, parent/child linkage, timestamps
- `StoryRecord`: story identity, owner, timestamps, media type, metadata
- `ErrorRecord`: stage, provider, target, stable error code, optional diagnostic context
- `RawCaptureRecord`: source endpoint, storage path, checksum, and relation to normalized entities

All output formats should derive from these models.

## Migration Strategy

Implementation should proceed in confidence-ordered phases.

### Phase 1

- add `Typer` CLI shell
- add `Pydantic` config and normalized record models
- add `Rich` terminal presentation
- wrap current username, browser-dump, and direct media workflows inside the new command graph

### Phase 2

- add `SQLAlchemy` SQLite metadata store
- add target provenance, dedupe, and freshness tracking
- add provider abstractions around current Instaloader and HTTP paths

### Phase 3

- add hashtag, location, followers, and following seed resolvers
- add explicit support tiers and capability preflight
- add auth/session management improvements

### Phase 4

- add likers, commenters, and stories
- add shared filters
- add optional `diskcache` for ephemeral discovery caching

### Phase 5

- add constrained browser fallback for auth bootstrap and target resolution
- migrate or expand the raw HTTP provider toward `HTTPX` where it materially improves observability or control
- add `orjson` where profiling shows JSON serialization overhead matters

## Testing Strategy

The implementation must avoid live-network dependence in default verification.

Required test layers:

- CLI parser coverage for every subcommand
- config validation tests
- normalized model serialization tests
- fixture-driven provider tests
- pagination and checkpoint tests
- dedupe and provenance tests
- support-tier and auth-preflight tests
- regression tests preserving current username and URL workflows

Live-network or authenticated smoke tests, if added, should be opt-in and out of default CI.

## Open Technical Constraints

- Instagram surfaces differ in reliability and auth requirements.
- Stories and second-order discovery paths may regress more often than profile or direct URL scraping.
- Session reuse is safer than repeated login attempts.
- Browser fallback must stay narrowly scoped or the architecture will drift toward an unstable automation stack.

## Recommended Next Step

Write the implementation plan against this design with concrete milestones, files, and verification steps before changing production code.

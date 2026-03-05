# Docs

Use this directory for architecture notes, scraping runbooks, and unified CLI
documentation.

The primary entrypoint is the Typer-based `instagram-scraper scrape ...`
command family. The implementation plan and design documents in `docs/plans/`
track the staged migration from the legacy standalone scripts to the unified
provider-driven pipeline.

Current unified pipeline behavior:

- stable profile and URL modes delegate into the legacy scrapers through provider wrappers
- `urls`, `hashtag`, `location`, `followers`, `following`, `likers`, `commenters`, and `stories` all resolve normalized targets
- every unified run initializes normalized artifact files such as `summary.json` and `targets.ndjson`
- support-state target dedupe is stored in `state.sqlite3`

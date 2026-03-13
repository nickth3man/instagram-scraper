# instagram-scraper

Unified one-shot Instagram scraping CLI with profile, URL, hashtag, location,
follow graph, interactions, and stories modes.

## Requirements

- `uv` installed
- Python 3.13 (managed by `uv` via `.python-version`)

## Setup

```bash
uv sync
```

## Authentication

Some modes require Instagram cookies, including `hashtag`, `location`,
`followers`, `following`, `likers`, `commenters`, `stories`,
`sync hashtag`, and `sync location`.

Prefer setting `IG_COOKIE_HEADER` in your shell or a project-local `.env`
file. The CLI and downloader load `.env` from the repository root
automatically.

```bash
# .env
IG_COOKIE_HEADER=sessionid=...
```

```bash
# bash
export IG_COOKIE_HEADER='sessionid=...'
```

```powershell
# PowerShell
$env:IG_COOKIE_HEADER = 'sessionid=...'
```

## Run

Run the package entrypoint:

```bash
uv run instagram-scraper
```

Run unified scrape modes:

```bash
uv run instagram-scraper scrape profile --username example
uv run instagram-scraper scrape url --url https://www.instagram.com/p/example/
uv run instagram-scraper scrape urls --input data/tool_dump.json
uv run instagram-scraper scrape hashtag --hashtag cats
uv run instagram-scraper scrape location --location nyc
uv run instagram-scraper scrape followers --username example
uv run instagram-scraper scrape stories --username example
uv run instagram-scraper sync hashtag --hashtag cats
uv run instagram-scraper sync location --location nyc
```

You can still use `--cookie-header` for one-off commands, but environment-based
auth keeps secrets out of shell history and matches the repository defaults.

Shared options implemented today:

```bash
--output-dir
--limit
--cookie-header  # optional override; prefer IG_COOKIE_HEADER or .env
```

Additional mode-specific support:

```bash
scrape urls: --resume --reset-output
scrape likers: --posts-limit
scrape commenters: --posts-limit
scrape stories: exactly one of --username or --hashtag
```

Legacy entrypoints remain available:

```bash
uv run instagram-scraper-profile
uv run instagram-scraper-browser-dump
uv run instagram-scraper-download-videos
```

Workflow modules and developer utilities now live under
`src/instagram_scraper/workflows/` rather than a separate `scripts/` directory.
Run them directly when you need the lower-level entrypoints:

```bash
uv run python -m instagram_scraper.workflows.browser_html data/tool_dump.json
uv run python -m instagram_scraper.workflows.failfast_instaloader --help
uv run python -m instagram_scraper.workflows.generate_extraction_commands
uv run scalene -m instagram_scraper.workflows.profile_profiler -- profile --username example
```

## Project Structure

```text
.
├── src/instagram_scraper/
├── tests/
├── docs/
├── pyproject.toml
├── uv.lock
└── README.md
```

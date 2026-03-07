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
uv run instagram-scraper scrape hashtag --hashtag cats --cookie-header "sessionid=..."
uv run instagram-scraper scrape location --location nyc --cookie-header "sessionid=..."
uv run instagram-scraper scrape followers --username example --cookie-header "sessionid=..."
uv run instagram-scraper scrape stories --username example --cookie-header "sessionid=..."
```

Shared options implemented today:

```bash
--output-dir
--limit
--cookie-header
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

## Project Structure

```text
.
├── src/instagram_scraper/
├── tests/
├── docs/
├── scripts/
├── pyproject.toml
├── uv.lock
└── README.md
```

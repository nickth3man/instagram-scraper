# instagram-scraper

Python project scaffolded with `uv` for Instagram scraping workflows.

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

Run the migrated scraper entrypoints:

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

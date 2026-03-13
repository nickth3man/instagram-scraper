# Instagram Scraper

Instagram profile scraper CLI for downloading recent post or reel media alongside comment and like exports.

## Features

- Scrapes the most recent posts and reels for a public profile
- Downloads media into per-post folders under `data/`
- Exports `comments.csv` and `likes.csv` for each scraped item
- Ships as a Typer-based CLI with a `uv` development workflow

## Requirements

- Python 3.11
- `uv`

## Setup

```bash
uv sync --all-groups
```

## Usage

```bash
uv run instagram-scraper scrape natgeo --limit 5
```

Optional output directory:

```bash
uv run instagram-scraper scrape natgeo --limit 5 --output ./tmp/natgeo
```

## Output Layout

```text
data/
└── natgeo/
    ├── post_ABC123/
    │   ├── comments.csv
    │   ├── likes.csv
    │   └── media.jpg
    └── reel_DEF456/
        ├── comments.csv
        ├── likes.csv
        └── media.mp4
```

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

Install the local Git hooks:

```bash
uv run pre-commit install
```

## Notes

- `likes.csv` may be incomplete because Instagram restricts liker visibility.
- Private accounts and some rate-limited data may require an authenticated Instaloader setup in future work.

## Project Layout

```text
.
├── pyproject.toml
├── src/instagram_scraper/
├── tests/
└── .github/workflows/ci.yml
```

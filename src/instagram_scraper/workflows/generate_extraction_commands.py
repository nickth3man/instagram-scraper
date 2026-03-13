# Copyright (c) 2026
"""Generate manual extraction instructions from a URL tool dump."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit

from instagram_scraper.workflows._workflow_inputs import load_tool_dump_urls

DEFAULT_INPUT_PATH = Path("data") / "believerofbuckets" / "tool_dump.json"
DEFAULT_LIMIT = 20
MANUAL_META_COMMAND = "document.querySelector('meta[name=description]')?.content"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for manual extraction instructions.

    Returns
    -------
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Generate manual extraction instructions for a small URL batch.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Write manual extraction instructions to stdout.

    Returns
    -------
        Process exit code.
    """
    args = parse_args(argv)
    urls = _load_urls(args.input, limit=args.limit)
    sys.stdout.write(_render_instructions(urls))
    return 0


def _load_urls(input_path: Path, *, limit: int) -> list[str]:
    return load_tool_dump_urls(input_path, limit=limit)


def _render_instructions(urls: list[str]) -> str:
    lines = [
        "Generated extraction commands. Run these in sequence:",
        f"{'=' * 60}",
    ]
    for url in urls:
        lines.extend(
            [
                "",
                f"# Extracting: {_extract_shortcode(url)}",
                f"Navigate to: {url}",
                f"Then run: {MANUAL_META_COMMAND}",
            ],
        )
    return "\n".join(lines) + "\n"


def _extract_shortcode(url: str) -> str:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    return parts[-1] if parts else ""


if __name__ == "__main__":
    raise SystemExit(main())

# Copyright (c) 2026
"""Generate manual extraction instructions from a URL tool dump."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

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
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        message = f"Expected a JSON object in {input_path}"
        raise TypeError(message)
    raw_urls = payload.get("urls")
    if not isinstance(raw_urls, list):
        message = f"Expected 'urls' to be a list in {input_path}"
        raise TypeError(message)
    resolved_limit = max(limit, 0)
    return [url for url in raw_urls[:resolved_limit] if isinstance(url, str)]


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

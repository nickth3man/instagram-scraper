# Copyright (c) 2026
"""Generate manual extraction commands for a small URL batch."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _main() -> int:
    data_dir = Path("data/believerofbuckets")
    input_file = data_dir / "tool_dump.json"

    with input_file.open(encoding="utf-8") as file:
        urls = json.load(file).get("urls", [])[:20]

    sys.stdout.write("Generated extraction commands. Run these in sequence:\n")
    sys.stdout.write(f"{'=' * 60}\n")

    for url in urls:
        shortcode = url.split("/")[-2]
        sys.stdout.write(f"\n# Extracting: {shortcode}\n")
        sys.stdout.write(f"Navigate to: {url}\n")
        sys.stdout.write(
            "Then run: document.querySelector('meta[name=description]')?.content\n",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

# Copyright (c) 2026
"""CLI helpers for the package entrypoint."""

import sys


def main() -> None:
    """Write the package banner to standard output."""
    # CLI programs usually communicate by printing text for the terminal to show.
    sys.stdout.write("Hello from instagram-scraper!\n")

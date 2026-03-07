# Copyright (c) 2026
"""Public package exports for instagram_scraper."""

# Re-export the Typer app and `main` for package consumers and console scripts.
from .cli import app, main

__all__ = ["app", "main"]

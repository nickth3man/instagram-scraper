# Copyright (c) 2026
"""Public package exports for instagram_scraper."""

# Re-export `main` so `import instagram_scraper` gives callers one obvious entrypoint.
from .cli import main

__all__ = ["main"]

# Copyright (c) 2026
"""Dispatch scraper workflows for profiling tools such as Scalene.

Examples
--------
    uv run scalene -m instagram_scraper.workflows.profile_profiler -- \
        profile --username cnn

    uv run scalene -m instagram_scraper.workflows.profile_profiler -- \
        download --output-dir data/test

    uv run scalene -m instagram_scraper.workflows.profile_profiler -- \
        browser-dump --tool-dump-path data/tool_dump.json
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from instagram_scraper.workflows.browser_dump import main as browser_dump_main
from instagram_scraper.workflows.profile import main as profile_main
from instagram_scraper.workflows.video_downloads import main as download_main

WorkflowMain = Callable[[], int | None]


@dataclass(frozen=True, slots=True)
class _EntryPoint:
    program_name: str
    callback: WorkflowMain


_ENTRYPOINTS = {
    "profile": _EntryPoint(
        program_name="scrape_instagram_profile",
        callback=profile_main,
    ),
    "download": _EntryPoint(
        program_name="download_instagram_videos",
        callback=download_main,
    ),
    "browser-dump": _EntryPoint(
        program_name="scrape_instagram_from_browser_dump",
        callback=browser_dump_main,
    ),
}


def main(argv: list[str] | None = None) -> int:
    """Run one supported workflow with profiler-friendly argument forwarding.

    Returns
    -------
        Process exit code.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return 1
    entry_point = _ENTRYPOINTS.get(args[0])
    if entry_point is None:
        return 1
    return _invoke(entry_point, args[1:])


def _invoke(entry_point: _EntryPoint, args: list[str]) -> int:
    original_argv = sys.argv[:]
    sys.argv = [entry_point.program_name, *args]
    try:
        result = entry_point.callback()
    finally:
        sys.argv = original_argv
    return 0 if result is None else result


if __name__ == "__main__":
    raise SystemExit(main())

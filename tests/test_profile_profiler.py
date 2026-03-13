from __future__ import annotations

import sys

from instagram_scraper.workflows import profile_profiler


def test_main_dispatches_profile_arguments(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_profile_main() -> None:
        recorded["argv"] = sys.argv[:]

    monkeypatch.setattr(profile_profiler, "profile_main", fake_profile_main)
    monkeypatch.setitem(
        profile_profiler._ENTRYPOINTS,
        "profile",
        profile_profiler._EntryPoint(
            program_name="scrape_instagram_profile",
            callback=fake_profile_main,
        ),
    )

    exit_code = profile_profiler.main(["profile", "--username", "cnn"])

    assert exit_code == 0
    assert recorded["argv"] == ["scrape_instagram_profile", "--username", "cnn"]


def test_main_dispatches_download_arguments(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_download_main() -> None:
        recorded["argv"] = sys.argv[:]

    monkeypatch.setattr(profile_profiler, "download_main", fake_download_main)
    monkeypatch.setitem(
        profile_profiler._ENTRYPOINTS,
        "download",
        profile_profiler._EntryPoint(
            program_name="download_instagram_videos",
            callback=fake_download_main,
        ),
    )

    exit_code = profile_profiler.main(["download", "--output-dir", "data/test"])

    assert exit_code == 0
    assert recorded["argv"] == [
        "download_instagram_videos",
        "--output-dir",
        "data/test",
    ]


def test_main_dispatches_browser_dump_arguments(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_browser_dump_main() -> None:
        recorded["argv"] = sys.argv[:]

    monkeypatch.setattr(profile_profiler, "browser_dump_main", fake_browser_dump_main)
    monkeypatch.setitem(
        profile_profiler._ENTRYPOINTS,
        "browser-dump",
        profile_profiler._EntryPoint(
            program_name="scrape_instagram_from_browser_dump",
            callback=fake_browser_dump_main,
        ),
    )

    exit_code = profile_profiler.main(
        ["browser-dump", "--tool-dump-path", "data/tool_dump.json"],
    )

    assert exit_code == 0
    assert recorded["argv"] == [
        "scrape_instagram_from_browser_dump",
        "--tool-dump-path",
        "data/tool_dump.json",
    ]


def test_main_returns_error_for_unknown_workflow() -> None:
    assert profile_profiler.main(["mystery-mode"]) == 1

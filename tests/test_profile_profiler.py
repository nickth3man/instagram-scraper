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


def test_main_returns_error_for_unknown_workflow() -> None:
    assert profile_profiler.main(["mystery-mode"]) == 1

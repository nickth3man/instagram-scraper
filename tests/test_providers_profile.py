from pathlib import Path

from instagram_scraper.providers.profile import ProfileScrapeProvider


def test_profile_provider_delegates_to_legacy_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    called: dict[str, object] = {}

    def fake_run_profile(*, username: str, output_dir: Path) -> dict[str, object]:
        called["username"] = username
        called["output_dir"] = output_dir
        return {"posts": 3, "comments": 4, "errors": 0}

    monkeypatch.setattr(
        "instagram_scraper.providers.profile.run_profile_scrape",
        fake_run_profile,
    )
    provider = ProfileScrapeProvider()
    summary = provider.run(username="example", output_dir=tmp_path)
    assert summary.mode == "profile"
    assert summary.posts == 3
    assert called["output_dir"] == tmp_path

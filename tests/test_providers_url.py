from pathlib import Path

import pytest

from instagram_scraper.providers.url import UrlScrapeProvider


def test_url_provider_delegates_to_browser_dump_runner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    called: dict[str, object] = {}

    def fake_run_urls(
        *,
        urls: list[str],
        output_dir: Path,
        cookie_header: str,
        **_: object,
    ) -> dict[str, object]:
        called["urls"] = urls
        called["output_dir"] = output_dir
        called["cookie_header"] = cookie_header
        return {"posts": 1, "comments": 2, "errors": 0}

    monkeypatch.setattr("instagram_scraper.providers.url.run_url_scrape", fake_run_urls)
    provider = UrlScrapeProvider()
    summary = provider.run(
        post_url="https://www.instagram.com/p/example/",
        output_dir=tmp_path,
        cookie_header="sessionid=abc",
    )
    assert summary.mode == "url"
    assert summary.posts == 1
    assert called["urls"] == ["https://www.instagram.com/p/example/"]


def test_url_provider_returns_no_urls_for_invalid_json_object(tmp_path: Path) -> None:
    input_path = tmp_path / "urls.json"
    input_path.write_text('{"unexpected": "value"}', encoding="utf-8")
    assert UrlScrapeProvider.resolve_targets(input_path=input_path) == []


def test_url_provider_forwards_runtime_controls(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    def fake_run_urls(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {"posts": 1, "comments": 2, "errors": 0, "processed": 1}

    input_path = tmp_path / "urls.txt"
    input_path.write_text("https://www.instagram.com/p/example/\n", encoding="utf-8")
    monkeypatch.setattr("instagram_scraper.providers.url.run_url_scrape", fake_run_urls)
    summary = UrlScrapeProvider.run_urls(
        input_path=input_path,
        output_dir=tmp_path,
        cookie_header="sessionid=abc",
        resume=True,
        reset_output=True,
        request_timeout=15,
        max_retries=2,
        checkpoint_every=7,
        min_delay=0.1,
        max_delay=0.4,
    )
    assert summary.mode == "urls"
    assert called["request_timeout"] == 15
    assert called["max_retries"] == 2
    assert called["checkpoint_every"] == 7
    assert called["min_delay"] == pytest.approx(0.1)
    assert called["max_delay"] == pytest.approx(0.4)
    assert called["resume"] is True
    assert called["reset_output"] is True


def test_url_provider_can_delegate_to_browser_html(
    monkeypatch,
    tmp_path: Path,
) -> None:
    called: dict[str, object] = {}

    def fake_run_browser_html_scrape(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {"posts": 1, "comments": 0, "errors": 0, "processed": 1}

    input_path = tmp_path / "urls.txt"
    input_path.write_text("https://www.instagram.com/p/example/\n", encoding="utf-8")
    monkeypatch.setattr(
        "instagram_scraper.providers.url.run_browser_html_scrape",
        fake_run_browser_html_scrape,
    )
    summary = UrlScrapeProvider.run_urls(
        input_path=input_path,
        output_dir=tmp_path,
        browser_html=True,
        cookies_file=tmp_path / "cookies.jsonc",
        storage_state=tmp_path / "state.json",
        user_data_dir=tmp_path / "profile",
        headed=True,
        timeout_ms=4321,
    )

    assert summary.mode == "urls"
    assert summary.posts == 1
    assert called["urls"] == ["https://www.instagram.com/p/example/"]
    assert called["headed"] is True
    assert called["timeout_ms"] == 4321


def test_url_provider_converts_string_browser_paths(
    monkeypatch,
    tmp_path: Path,
) -> None:
    called: dict[str, object] = {}

    def fake_run_browser_html_scrape(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {"posts": 1, "comments": 0, "errors": 0, "processed": 1}

    monkeypatch.setattr(
        "instagram_scraper.providers.url.run_browser_html_scrape",
        fake_run_browser_html_scrape,
    )
    input_path = tmp_path / "urls.txt"
    input_path.write_text("https://www.instagram.com/p/example/\n", encoding="utf-8")

    UrlScrapeProvider.run_urls(
        input_path=input_path,
        output_dir=tmp_path,
        browser_html=True,
        cookies_file=str(tmp_path / "cookies.jsonc"),
        storage_state=str(tmp_path / "state.json"),
        user_data_dir=str(tmp_path / "profile"),
    )

    assert called["cookies_file"] == tmp_path / "cookies.jsonc"
    assert called["storage_state"] == tmp_path / "state.json"
    assert called["user_data_dir"] == tmp_path / "profile"

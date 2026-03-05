from pathlib import Path

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

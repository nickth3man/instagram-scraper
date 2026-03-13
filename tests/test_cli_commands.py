from typing import cast

from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_profile_subcommand_invokes_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(app, ["scrape", "profile", "--username", "example"])
    assert result.exit_code == 0
    assert called["mode"] == "profile"


def test_urls_subcommand_invokes_pipeline(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    input_path = tmp_path / "urls.txt"
    input_path.write_text("https://www.instagram.com/p/example/\n", encoding="utf-8")
    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(app, ["scrape", "urls", "--input", str(input_path)])
    assert result.exit_code == 0
    assert called["mode"] == "urls"


def test_url_subcommand_forwards_browser_html_options(monkeypatch) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(
        app,
        [
            "scrape",
            "--browser-html",
            "url",
            "--url",
            "https://www.instagram.com/p/example/",
        ],
    )
    assert result.exit_code == 0
    assert called["mode"] == "url"
    kwargs = cast("dict[str, object]", called["kwargs"])
    assert kwargs["browser_html"] is True


def test_url_subcommand_forwards_browser_session_options(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    cookies_file = tmp_path / "cookies.jsonc"
    storage_state = tmp_path / "state.json"
    user_data_dir = tmp_path / "profile"
    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(
        app,
        [
            "scrape",
            "--browser-html",
            "url",
            "--cookies-file",
            str(cookies_file),
            "--storage-state",
            str(storage_state),
            "--user-data-dir",
            str(user_data_dir),
            "--headed",
            "--timeout-ms",
            "4321",
            "--url",
            "https://www.instagram.com/p/example/",
        ],
    )
    assert result.exit_code == 0
    kwargs = cast("dict[str, object]", called["kwargs"])
    assert kwargs["cookies_file"] == cookies_file
    assert kwargs["storage_state"] == storage_state
    assert kwargs["user_data_dir"] == user_data_dir
    assert kwargs["headed"] is True
    assert kwargs["timeout_ms"] == 4321


def test_url_subcommand_passes_runtime_controls(monkeypatch) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(
        app,
        [
            "scrape",
            "--raw-captures",
            "--request-timeout",
            "15",
            "--max-retries",
            "2",
            "--checkpoint-every",
            "7",
            "url",
            "--url",
            "https://www.instagram.com/p/example/",
        ],
    )
    assert result.exit_code == 0
    assert called["mode"] == "url"
    kwargs = cast("dict[str, object]", called["kwargs"])
    assert kwargs["raw_captures"] is True
    assert kwargs["request_timeout"] == 15
    assert kwargs["max_retries"] == 2
    assert kwargs["checkpoint_every"] == 7


def test_runtime_controls_do_not_leak_between_cli_invocations(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[dict[str, object]] = []

    def fake_run(mode: str, **kwargs: object) -> int:
        calls.append({"mode": mode, "kwargs": kwargs})
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    first = runner.invoke(
        app,
        [
            "scrape",
            "--raw-captures",
            "url",
            "--url",
            "https://www.instagram.com/p/example/",
        ],
    )
    second = runner.invoke(
        app,
        [
            "scrape",
            "url",
            "--url",
            "https://www.instagram.com/p/example-2/",
        ],
    )
    assert first.exit_code == 0
    assert second.exit_code == 0
    first_kwargs = cast("dict[str, object]", calls[0]["kwargs"])
    second_kwargs = cast("dict[str, object]", calls[1]["kwargs"])
    assert first_kwargs["raw_captures"] is True
    assert second_kwargs["raw_captures"] is False

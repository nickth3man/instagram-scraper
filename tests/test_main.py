import importlib
from pathlib import Path

from typer.testing import CliRunner

runner = CliRunner()


def test_scrape_command_passes_arguments(monkeypatch) -> None:
    main = importlib.import_module("instagram_scraper.main")

    captured: dict[str, object] = {}

    def fake_scrape_profile(username: str, limit: int, output: Path | None) -> None:
        captured["username"] = username
        captured["limit"] = limit
        captured["output"] = output

    monkeypatch.setattr(main, "scrape_profile", fake_scrape_profile)

    result = runner.invoke(
        main.app,
        ["natgeo", "--limit", "3", "--output", "tmp/output"],
    )

    assert result.exit_code == 0
    assert captured == {
        "username": "natgeo",
        "limit": 3,
        "output": Path("tmp/output"),
    }

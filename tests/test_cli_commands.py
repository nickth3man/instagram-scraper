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

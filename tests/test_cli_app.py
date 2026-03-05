from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_scrape_group_is_available() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.stdout
    assert "url" in result.stdout

import importlib

from typer.testing import CliRunner


def test_package_exports_cli_app() -> None:
    module = importlib.import_module("instagram_scraper")
    runner = CliRunner()
    result = runner.invoke(module.app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.stdout

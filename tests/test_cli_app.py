from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_scrape_group_is_available() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.stdout
    assert "url" in result.stdout


def test_scrape_help_lists_all_unified_modes() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    for command in (
        "profile",
        "url",
        "urls",
        "hashtag",
        "location",
        "followers",
        "following",
        "likers",
        "commenters",
        "stories",
    ):
        assert command in result.stdout

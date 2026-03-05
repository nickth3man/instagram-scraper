import importlib


def test_main_prints_banner(capsys) -> None:
    # Import the package the same way a normal user would.
    module = importlib.import_module("instagram_scraper")
    module.main()
    captured = capsys.readouterr()
    assert "instagram-scraper" in captured.out

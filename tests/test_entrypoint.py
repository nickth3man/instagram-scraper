import importlib


def test_main_prints_banner(capsys) -> None:
    module = importlib.import_module("instagram_scraper")
    module.main()
    captured = capsys.readouterr()
    assert "instagram-scraper" in captured.out

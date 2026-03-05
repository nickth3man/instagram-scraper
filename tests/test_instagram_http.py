import importlib

instagram_http = importlib.import_module("instagram_scraper._instagram_http")


def test_build_instagram_client_sets_browser_headers() -> None:
    client = instagram_http.build_instagram_client("")
    assert client.headers["Referer"] == "https://www.instagram.com/"
    client.close()

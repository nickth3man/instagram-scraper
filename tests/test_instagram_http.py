import importlib

instagram_http = importlib.import_module(
    "instagram_scraper.infrastructure.instagram_http",
)


def test_build_instagram_client_sets_browser_headers() -> None:
    with instagram_http.build_instagram_client("") as client:
        assert client.headers["Referer"] == "https://www.instagram.com/"


def test_build_instagram_client_copies_csrftoken_header() -> None:
    cookie_header = "csrftoken=abc; sessionid=def"
    with instagram_http.build_instagram_client(cookie_header) as client:
        assert client.headers["X-CSRFToken"] == "abc"

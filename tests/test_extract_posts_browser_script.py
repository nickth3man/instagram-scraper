from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

pytest.importorskip("playwright")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "extract_posts_browser.py"
SPEC = spec_from_file_location("extract_posts_browser", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    message = f"Unable to load script module from {SCRIPT_PATH}"
    raise RuntimeError(message)
extract_posts_browser = module_from_spec(SPEC)
sys.modules["extract_posts_browser"] = extract_posts_browser
SPEC.loader.exec_module(extract_posts_browser)


def test_extract_post_row_from_html_uses_embedded_json_values() -> None:
    html = """
    <html>
      <head>
        <meta property="al:ios:url" content="instagram://media?id=1234567890" />
      </head>
      <body>
        <script type="application/json">
          {"shortcode":"abc123","edge_media_preview_like":{"count":321},
          "edge_media_to_parent_comment":{"count":17},
          "caption":{"text":"Caption from JSON"},
          "taken_at_timestamp":1700000000,"is_video":true}
        </script>
      </body>
    </html>
    """

    row = extract_posts_browser._extract_post_row_from_html(
        html,
        "https://www.instagram.com/p/abc123/",
    )

    assert row == {
        "media_id": "1234567890",
        "shortcode": "abc123",
        "post_url": "https://www.instagram.com/p/abc123/",
        "type": 2,
        "taken_at_utc": 1700000000,
        "caption": "Caption from JSON",
        "like_count": 321,
        "comment_count": 17,
    }


def test_extract_post_row_from_html_falls_back_to_meta_description() -> None:
    html = """
    <html>
      <head>
        <meta property="al:ios:url" content="instagram://media?id=999999" />
        <meta
          property="og:description"
          content="1,234 likes, 56 comments - bucketlover:
          &quot;Caption from meta&quot;"
        />
      </head>
      <body></body>
    </html>
    """

    row = extract_posts_browser._extract_post_row_from_html(
        html,
        "https://www.instagram.com/p/meta123/",
    )

    assert row["media_id"] == "999999"
    assert row["shortcode"] == "meta123"
    assert row["type"] == 1
    assert row["taken_at_utc"] is None
    assert row["caption"] == "Caption from meta"
    assert row["like_count"] == 1234
    assert row["comment_count"] == 56


def test_load_playwright_cookies_supports_jsonc(tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.jsonc"
    cookie_file.write_text(
        """
        [
          // session cookie
          {
            "name": "sessionid",
            "value": "abc",
            "domain": ".instagram.com",
            "path": "/",
            "secure": true,
            "httpOnly": true,
            "sameSite": "no_restriction",
            "expirationDate": 1804670833.0
          }
        ]
        """,
        encoding="utf-8",
    )

    cookies = extract_posts_browser._load_playwright_cookies(cookie_file)

    assert cookies == [
        {
            "name": "sessionid",
            "value": "abc",
            "domain": ".instagram.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None",
            "expires": 1804670833.0,
        },
    ]

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from instagram_scraper import download_instagram_videos as videos
from instagram_scraper import scrape_instagram_profile as profile


def test_no_hardcoded_specific_username_literals() -> None:
    files = [
        Path("src/instagram_scraper/scrape_instagram_from_browser_dump.py"),
        Path("src/instagram_scraper/download_instagram_videos.py"),
    ]
    for file_path in files:
        assert "believerofbuckets" not in file_path.read_text(encoding="utf-8")


def test_browser_dump_defaults_respect_data_dir_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("INSTAGRAM_DATA_DIR", str(tmp_path / "ig-data"))
    monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
    monkeypatch.setattr(sys, "argv", ["prog"])

    module = importlib.import_module(
        "instagram_scraper.scrape_instagram_from_browser_dump",
    )
    module = importlib.reload(module)

    cfg = module.parse_args()
    assert cfg.output_dir.parent == (tmp_path / "ig-data")
    assert cfg.tool_dump_path.parent == (tmp_path / "ig-data")


def test_fetch_media_id_uses_shortcode_api(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(
        "instagram_scraper.scrape_instagram_from_browser_dump",
    )

    class FakeJsonResponse:
        headers = {"content-type": "application/json"}
        text = "{}"

        def __init__(self, payload: dict):
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    calls: list[str] = []

    def fake_request_with_retry(session, url, cfg, params=None):  # noqa: ANN001
        calls.append(url)
        if "/api/v1/media/shortcode/" in url:
            return FakeJsonResponse({"items": [{"id": "123456789"}]}), None
        return None, "http_404"

    monkeypatch.setattr(module, "request_with_retry", fake_request_with_retry)

    cfg = module.Config(
        tool_dump_path=Path("unused"),
        output_dir=Path("unused"),
        resume=False,
        reset_output=False,
        start_index=0,
        limit=None,
        checkpoint_every=10,
        max_comment_pages=5,
        min_delay=0.0,
        max_delay=0.0,
        request_timeout=10,
        max_retries=1,
        base_retry_seconds=0.1,
        cookie_header="",
    )

    media_id, error = module.fetch_media_id(
        object(),
        "https://www.instagram.com/p/example/",
        "example",
        cfg,
    )
    assert media_id == "123456789"
    assert error is None
    assert any("/api/v1/media/shortcode/" in url for url in calls)


def test_checkpoint_saved_after_error_before_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    module = importlib.import_module(
        "instagram_scraper.scrape_instagram_from_browser_dump",
    )

    tool_dump = tmp_path / "tool_dump.json"
    tool_dump.write_text(
        json.dumps(
            {
                "count": 2,
                "urls": [
                    "https://www.instagram.com/not-a-post/",
                    "https://www.instagram.com/p/SHORTCODE/",
                ],
            },
        ),
        encoding="utf-8",
    )

    class DummySession:
        def close(self) -> None:
            return None

    def fake_build_session(cookie_header: str):
        return DummySession()

    def crash_fetch_media_id(session, post_url, shortcode, cfg):  # noqa: ANN001
        raise RuntimeError("boom during media id")

    monkeypatch.setattr(module, "build_session", fake_build_session)
    monkeypatch.setattr(module, "fetch_media_id", crash_fetch_media_id)

    output_dir = tmp_path / "output"
    cfg = module.Config(
        tool_dump_path=tool_dump,
        output_dir=output_dir,
        resume=False,
        reset_output=True,
        start_index=0,
        limit=None,
        checkpoint_every=20,
        max_comment_pages=5,
        min_delay=0.0,
        max_delay=0.0,
        request_timeout=10,
        max_retries=1,
        base_retry_seconds=0.1,
        cookie_header="",
    )

    with pytest.raises(RuntimeError, match="boom during media id"):
        module.run(cfg)

    checkpoint = json.loads((output_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["processed"] == 1
    assert checkpoint["next_index"] == 1


def test_download_video_file_cleans_partial_file_on_write_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class FakeResponse:
        def iter_content(self, chunk_size: int):  # noqa: ARG002
            yield b"partial-data"
            raise OSError("disk write interrupted")

    def fake_request_with_retry(session, url, cfg, stream=False):  # noqa: ANN001, ARG001
        return FakeResponse(), None

    monkeypatch.setattr(videos, "request_with_retry", fake_request_with_retry)

    cfg = videos.Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        resume=False,
        reset_output=False,
        min_delay=0.0,
        max_delay=0.0,
        max_retries=1,
        timeout=10,
        checkpoint_every=10,
        limit=None,
        cookie_header="",
    )
    destination = tmp_path / "video.mp4"
    ok, error = videos.download_video_file(
        object(),
        "https://example.com/video.mp4",
        destination,
        cfg,
    )
    assert ok is False
    assert error is not None and error.startswith("file_write_error:")
    assert not destination.exists()
    assert not any(tmp_path.glob("video.mp4.*.part"))


def test_comment_to_dict_uses_comment_like_count_key() -> None:
    owner = SimpleNamespace(username="alice", userid=42)
    comment = SimpleNamespace(
        id=7,
        owner=owner,
        created_at_utc=None,
        text="hi",
        likes_count=3,
    )

    row = profile.comment_to_dict(comment)
    assert row["comment_like_count"] == 3
    assert "likes_count" not in row

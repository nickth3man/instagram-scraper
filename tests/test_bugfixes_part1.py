import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    import requests

from instagram_scraper.workflows import _browser_dump_fetch as browser_dump_fetch
from instagram_scraper.workflows import _browser_dump_io as browser_dump_io
from instagram_scraper.workflows import _browser_dump_process as browser_dump_process
from instagram_scraper.workflows import (
    _video_download_download as video_download_download,
)
from instagram_scraper.workflows import profile
from instagram_scraper.workflows import video_downloads as videos


def _shared_io_module():
    return importlib.import_module("instagram_scraper.infrastructure.files")


def test_no_hardcoded_specific_username_literals() -> None:
    # Guard against reintroducing a personal username that would break reuse.
    files = [
        Path("src/instagram_scraper/workflows/browser_dump.py"),
        Path("src/instagram_scraper/workflows/video_downloads.py"),
    ]
    for file_path in files:
        assert "believerofbuckets" not in file_path.read_text(encoding="utf-8")


def test_browser_dump_defaults_respect_data_dir_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Reload the module after changing environment variables so default paths are
    # recomputed from the test values instead of the real machine values.
    monkeypatch.setenv("INSTAGRAM_DATA_DIR", str(tmp_path / "ig-data"))
    monkeypatch.delenv("INSTAGRAM_USERNAME", raising=False)
    monkeypatch.setattr(sys, "argv", ["prog"])

    module = importlib.import_module(
        "instagram_scraper.workflows.browser_dump",
    )
    module = importlib.reload(module)

    cfg = module.parse_args()
    assert cfg.output_dir.parent == (tmp_path / "ig-data")
    assert cfg.tool_dump_path.parent == (tmp_path / "ig-data")


def test_fetch_media_id_uses_shortcode_api(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(
        "instagram_scraper.workflows.browser_dump",
    )

    class FakeJsonResponse:
        def __init__(self, payload: dict):
            self.headers = {"content-type": "application/json"}
            self.text = "{}"
            self._payload = payload

        def json(self) -> dict:
            return self._payload

    calls: list[str] = []

    def fake_request_with_retry(session, url, cfg, params=None):
        # Return a successful fake response only for the shortcode endpoint.
        calls.append(url)
        if "/api/v1/media/shortcode/" in url:
            return FakeJsonResponse({"items": [{"id": "123456789"}]}), None
        return None, "http_404"

    monkeypatch.setattr(
        browser_dump_fetch,
        "_request_with_retry",
        fake_request_with_retry,
    )

    cfg = module.Config(
        tool_dump_path=Path("unused"),
        output_dir=Path("unused"),
        should_resume=False,
        should_reset_output=False,
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = importlib.import_module(
        "instagram_scraper.workflows.browser_dump",
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

    def crash_fetch_media_id(session, post_url, shortcode, cfg):
        raise RuntimeError("boom during media id")

    monkeypatch.setattr(module, "_build_session", fake_build_session)
    monkeypatch.setattr(browser_dump_process, "fetch_media_id", crash_fetch_media_id)

    output_dir = tmp_path / "output"
    cfg = module.Config(
        tool_dump_path=tool_dump,
        output_dir=output_dir,
        should_resume=False,
        should_reset_output=True,
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

    # The first URL is bad on purpose. The checkpoint proves the scraper recorded
    # that progress before the second URL crashed.
    checkpoint = json.loads(
        (output_dir / "checkpoint.json").read_text(encoding="utf-8"),
    )
    assert checkpoint["processed"] == 1
    assert checkpoint["next_index"] == 1


def test_process_url_missing_shortcode_records_error_and_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = importlib.import_module(
        "instagram_scraper.workflows.browser_dump",
    )

    tool_dump = tmp_path / "tool_dump.json"
    tool_dump.write_text(
        json.dumps(
            {
                "count": 1,
                "urls": ["https://www.instagram.com/not-a-post/"],
            },
        ),
        encoding="utf-8",
    )

    delay_calls = 0

    def fake_randomized_delay(min_delay, max_delay):
        del min_delay, max_delay
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(
        browser_dump_process,
        "_randomized_delay",
        fake_randomized_delay,
    )

    cfg = module.Config(
        tool_dump_path=tool_dump,
        output_dir=tmp_path / "output",
        should_resume=False,
        should_reset_output=True,
        start_index=0,
        limit=None,
        checkpoint_every=50,
        max_comment_pages=5,
        min_delay=0.0,
        max_delay=0.0,
        request_timeout=10,
        max_retries=1,
        base_retry_seconds=0.1,
        cookie_header="",
    )
    summary = module.run(cfg)

    assert summary["processed"] == 1
    assert summary["errors"] == 1
    assert summary["posts"] == 0
    assert summary["comments"] == 0
    assert delay_calls == 0

    errors_path = cfg.output_dir / "errors.ndjson"
    error_rows = [
        json.loads(line)
        for line in errors_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(error_rows) == 1
    assert error_rows[0]["stage"] == "extract_shortcode"
    assert error_rows[0]["error"] == "missing_shortcode"

    checkpoint_path = cfg.output_dir / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["next_index"] == 1
    assert checkpoint["processed"] == 1
    assert checkpoint["errors"] == 1
    assert checkpoint["completed"] is True


def test_process_url_media_info_failure_preserves_delay_and_checkpoint_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = importlib.import_module(
        "instagram_scraper.workflows.browser_dump",
    )

    tool_dump = tmp_path / "tool_dump.json"
    tool_dump.write_text(
        json.dumps(
            {
                "count": 1,
                "urls": ["https://www.instagram.com/p/SHORTCODE/"],
            },
        ),
        encoding="utf-8",
    )

    cfg = module.Config(
        tool_dump_path=tool_dump,
        output_dir=tmp_path / "output",
        should_resume=False,
        should_reset_output=True,
        start_index=0,
        limit=None,
        checkpoint_every=50,
        max_comment_pages=5,
        min_delay=0.0,
        max_delay=0.0,
        request_timeout=10,
        max_retries=1,
        base_retry_seconds=0.1,
        cookie_header="",
    )

    delay_calls = 0
    checkpoint_states: list[dict[str, object]] = []

    original_save_checkpoint = browser_dump_io._save_checkpoint

    def fake_fetch_media_id(session, post_url, shortcode, cfg):
        del session, post_url, shortcode, cfg
        return "999", None

    def fake_fetch_media_info(session, media_id, cfg):
        del session, media_id, cfg
        return None, "media_info_request_failed"

    def save_checkpoint_spy(output_dir, state):
        checkpoint_states.append(dict(state))
        original_save_checkpoint(output_dir, state)

    def fake_randomized_delay(min_delay, max_delay):
        del min_delay, max_delay
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(browser_dump_process, "fetch_media_id", fake_fetch_media_id)
    monkeypatch.setattr(
        browser_dump_process,
        "_fetch_media_info",
        fake_fetch_media_info,
    )
    monkeypatch.setattr(browser_dump_io, "_save_checkpoint", save_checkpoint_spy)
    monkeypatch.setattr(module, "_save_checkpoint", save_checkpoint_spy)
    monkeypatch.setattr(
        browser_dump_process,
        "_randomized_delay",
        fake_randomized_delay,
    )

    summary = module.run(cfg)

    assert summary["processed"] == 1
    assert summary["errors"] == 1
    assert summary["posts"] == 0
    assert summary["comments"] == 0
    assert delay_calls == 2

    errors_path = cfg.output_dir / "errors.ndjson"
    error_rows = [
        json.loads(line)
        for line in errors_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(error_rows) == 1
    assert error_rows[0]["stage"] == "fetch_media_info"
    assert error_rows[0]["error"] == "media_info_request_failed"

    assert len(checkpoint_states) == 2
    assert checkpoint_states[0]["next_index"] == 1
    assert checkpoint_states[0]["processed"] == 0
    assert checkpoint_states[0]["errors"] == 1
    assert "completed" not in checkpoint_states[0]

    checkpoint_path = cfg.output_dir / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["next_index"] == 1
    assert checkpoint["processed"] == 1
    assert checkpoint["errors"] == 1
    assert checkpoint["completed"] is True


def test_download_video_file_cleans_partial_file_on_write_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeResponse:
        def iter_content(self, chunk_size: int):  # noqa: ARG002
            # Simulate "download started, disk failed halfway through".
            yield b"partial-data"
            raise OSError("disk write interrupted")

    def fake_request_with_retry(session, url, cfg, stream=False):
        return FakeResponse(), None

    monkeypatch.setattr(
        video_download_download,
        "_request_with_retry",
        fake_request_with_retry,
    )

    cfg = videos.Config(
        output_dir=tmp_path,
        posts_csv=tmp_path / "posts.csv",
        comments_csv=tmp_path / "comments.csv",
        should_resume=False,
        should_reset_output=True,
        min_delay=0.0,
        max_delay=0.0,
        max_retries=1,
        timeout=10,
        checkpoint_every=1,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=1,
    )
    destination = tmp_path / "video.mp4"
    ok, error = videos.download_video_file(
        cast("requests.Session", object()),
        "https://example.com/video.mp4",
        destination,
        cfg,
    )
    # A failed download should not leave behind either a final file or a temp file.
    assert ok is False
    assert error is not None and error.startswith("file_write_error:")
    assert not destination.exists()
    assert not any(tmp_path.glob("video.mp4.*.part"))


def test_comment_to_dict_uses_comment_like_count_key() -> None:
    # Build a tiny fake comment object that looks enough like Instaloader's real one.
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


def test_profile_write_outputs_uses_atomic_write_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writes: list[tuple[Path, str]] = []

    def atomic_write_spy(path: Path, content: str) -> None:
        writes.append((path, content))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(profile, "atomic_write_text", atomic_write_spy)
    write_outputs = profile.__dict__["_write_outputs"]

    write_outputs(
        tmp_path,
        {"target_profile": "alice", "posts": []},
        [
            {
                "shortcode": "SC1",
                "post_url": "https://www.instagram.com/p/SC1/",
                "date_utc": "2026-01-01T00:00:00+00:00",
                "caption": "caption",
                "likes": 1,
                "comments_count_reported": 0,
                "is_video": False,
                "typename": "GraphImage",
                "owner_username": "alice",
                "comments": [],
            },
        ],
        [
            {
                "post_shortcode": "SC1",
                "id": "c1",
                "parent_id": None,
                "created_at_utc": "2026-01-01T00:00:00+00:00",
                "text": "hello",
                "comment_like_count": 1,
                "owner_username": "alice",
                "owner_id": "42",
            },
        ],
    )

    assert [path.name for path, _ in writes] == ["instagram_dataset.json"]
    assert (tmp_path / "posts.csv").exists()
    assert (tmp_path / "comments.csv").exists()

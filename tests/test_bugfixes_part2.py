import json
from pathlib import Path

import pytest

from instagram_scraper.workflows import (
    _video_download_download as video_download_download,
)
from instagram_scraper.workflows import (
    _video_download_process as video_download_process,
)
from instagram_scraper.workflows import video_downloads as videos
from instagram_scraper.workflows.video_downloads import (
    _DownloadContext,
    _initial_metrics,
    _prepare_output,
)


def test_download_entries_writes_index_and_error_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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
        checkpoint_every=10,
        limit=None,
        cookie_header="",
        max_concurrent_downloads=1,
    )
    paths = _prepare_output(cfg)
    metrics = _initial_metrics(None)
    context = _DownloadContext(
        cfg=cfg,
        session=object(),
        paths=paths,
        comments_by_shortcode={},
        metrics=metrics,
        completed=set(),
    )
    post = videos.__dict__["_PostTarget"](
        shortcode="SC1",
        media_id="MID1",
        post_url="https://www.instagram.com/p/SC1/",
    )
    post_dir = paths["videos_root"] / post.shortcode
    post_dir.mkdir(parents=True, exist_ok=True)
    video_entries = [
        {"position": 1, "video_url": "https://cdn.example.com/good.mp4"},
        {"position": 2, "video_url": "https://cdn.example.com/bad.mp4"},
    ]

    def fake_download_video_file(session, video_url, destination, inner_cfg):
        del session, inner_cfg
        if "bad" in video_url:
            return False, "video_download_failed"
        destination.write_bytes(b"ok")
        return True, None

    monkeypatch.setattr(
        video_download_download,
        "download_video_file",
        fake_download_video_file,
    )

    downloaded = videos.__dict__["_download_entries"](
        context,
        post,
        video_entries,
        post_dir,
    )

    assert len(downloaded) == 1
    assert downloaded[0]["shortcode"] == "SC1"
    assert downloaded[0]["position"] == 1
    assert metrics["downloaded_files"] == 1
    assert metrics["errors"] == 1
    assert metrics["processed"] == 0

    index_rows = (cfg.output_dir / "videos_index.csv").read_text(encoding="utf-8")
    error_rows = (cfg.output_dir / "videos_errors.csv").read_text(encoding="utf-8")
    assert "SC1" in index_rows
    assert "good.mp4" in index_rows
    assert "download_video_file" in error_rows
    assert "video_download_failed" in error_rows


def test_process_post_row_success_writes_payload_and_checkpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
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
    paths = videos.__dict__["_prepare_output"](cfg)
    context = _DownloadContext(
        cfg=cfg,
        session=object(),
        paths=paths,
        comments_by_shortcode={
            "SC2": [
                {
                    "media_id": "MID2",
                    "shortcode": "SC2",
                    "post_url": "https://www.instagram.com/p/SC2/",
                    "id": "11",
                    "created_at_utc": "2026-01-01T00:00:00Z",
                    "text": "hello",
                    "comment_like_count": "0",
                    "owner_username": "alice",
                    "owner_id": "123",
                },
            ],
        },
        metrics=_initial_metrics(None),
        completed=set(),
    )

    def fake_fetch_media_info(session, media_id, inner_cfg):
        del session, media_id, inner_cfg
        return {
            "media_type": videos.MEDIA_TYPE_VIDEO,
            "video_versions": [
                {
                    "width": 1080,
                    "height": 1920,
                    "url": "https://cdn.example.com/sc2.mp4",
                },
            ],
        }, None

    def fake_download_video_file(session, video_url, destination, inner_cfg):
        del session, video_url, inner_cfg
        destination.write_bytes(b"video-bytes")
        return True, None

    delay_calls = 0

    def fake_randomized_delay(inner_cfg, *, scale=1.0):
        del inner_cfg, scale
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(
        video_download_process,
        "_fetch_media_info",
        fake_fetch_media_info,
    )
    monkeypatch.setattr(
        video_download_download,
        "download_video_file",
        fake_download_video_file,
    )
    monkeypatch.setattr(
        video_download_process,
        "_randomized_delay",
        fake_randomized_delay,
    )

    row = {
        "shortcode": "SC2",
        "media_id": "MID2",
        "post_url": "https://www.instagram.com/p/SC2/",
        "caption": "caption text",
        "comment_count": "1",
    }
    videos.__dict__["_process_post_row"](context, row)

    assert context.metrics["processed"] == 1
    assert context.metrics["downloaded_files"] == 1
    assert context.metrics["errors"] == 0
    assert context.metrics["skipped_no_video"] == 0
    assert delay_calls == 1
    assert "SC2" in context.completed

    post_dir = cfg.output_dir / "videos" / "SC2"
    caption = (post_dir / "caption.txt").read_text(encoding="utf-8")
    metadata = json.loads((post_dir / "metadata.json").read_text(encoding="utf-8"))
    comments_csv = (post_dir / "comments.csv").read_text(encoding="utf-8")
    checkpoint = json.loads(
        (cfg.output_dir / "videos_checkpoint.json").read_text(encoding="utf-8"),
    )

    assert caption == "caption text"
    assert metadata["shortcode"] == "SC2"
    assert metadata["media_id"] == "MID2"
    assert metadata["comments_saved"] == 1
    assert len(metadata["video_files"]) == 1
    assert "owner_username" in comments_csv
    assert checkpoint["processed"] == 1
    assert checkpoint["downloaded_files"] == 1
    assert checkpoint["completed_shortcodes"] == ["SC2"]

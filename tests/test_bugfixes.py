import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from instagram_scraper import download_instagram_videos as videos
from instagram_scraper import scrape_instagram_profile as profile


def _shared_io_module():
    return importlib.import_module("instagram_scraper._shared_io")


def test_no_hardcoded_specific_username_literals() -> None:
    # Guard against reintroducing a personal username that would break reuse.
    files = [
        Path("src/instagram_scraper/scrape_instagram_from_browser_dump.py"),
        Path("src/instagram_scraper/download_instagram_videos.py"),
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

    monkeypatch.setattr(module, "_request_with_retry", fake_request_with_retry)

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

    def crash_fetch_media_id(session, post_url, shortcode, cfg):
        raise RuntimeError("boom during media id")

    monkeypatch.setattr(module, "_build_session", fake_build_session)
    monkeypatch.setattr(module, "fetch_media_id", crash_fetch_media_id)

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
        "instagram_scraper.scrape_instagram_from_browser_dump",
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

    def fake_randomized_delay(cfg, *, extra_scale=1.0):
        del cfg, extra_scale
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(module, "_randomized_delay", fake_randomized_delay)

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
        "instagram_scraper.scrape_instagram_from_browser_dump",
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

    original_save_checkpoint = module.__dict__["_save_checkpoint"]

    def fake_fetch_media_id(session, post_url, shortcode, cfg):
        del session, post_url, shortcode, cfg
        return "999", None

    def fake_fetch_media_info(session, media_id, cfg):
        del session, media_id, cfg
        return None, "media_info_request_failed"

    def save_checkpoint_spy(output_dir, state):
        checkpoint_states.append(dict(state))
        original_save_checkpoint(output_dir, state)

    def fake_randomized_delay(cfg, *, extra_scale=1.0):
        del cfg, extra_scale
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(module, "fetch_media_id", fake_fetch_media_id)
    monkeypatch.setattr(module, "_fetch_media_info", fake_fetch_media_info)
    monkeypatch.setattr(module, "_save_checkpoint", save_checkpoint_spy)
    monkeypatch.setattr(module, "_randomized_delay", fake_randomized_delay)

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

    monkeypatch.setattr(videos, "_request_with_retry", fake_request_with_retry)

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
        object(),
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
    paths = videos.__dict__["_prepare_output"](cfg)
    metrics = videos.__dict__["_initial_metrics"](None)
    context = videos.__dict__["_DownloadContext"](
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

    monkeypatch.setattr(videos, "download_video_file", fake_download_video_file)

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
    context = videos.__dict__["_DownloadContext"](
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
        metrics=videos.__dict__["_initial_metrics"](None),
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

    monkeypatch.setattr(videos, "_fetch_media_info", fake_fetch_media_info)
    monkeypatch.setattr(videos, "download_video_file", fake_download_video_file)
    monkeypatch.setattr(videos, "_randomized_delay", fake_randomized_delay)

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


def test_downloader_post_payload_writes_use_atomic_shared_io(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_dict = videos.__dict__
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
    prepare_output = module_dict["_prepare_output"]
    write_post_payload = module_dict["_write_post_payload"]
    write_post_metadata = module_dict["_write_post_metadata"]
    post_metadata = module_dict["_post_metadata"]
    post_target = module_dict["_PostTarget"]

    paths = prepare_output(cfg)
    context = module_dict["_DownloadContext"](
        cfg=cfg,
        session=object(),
        paths=paths,
        comments_by_shortcode={},
        metrics=module_dict["_initial_metrics"](None),
        completed=set(),
    )

    writes: list[tuple[Path, str]] = []

    def atomic_write_spy(path: Path, content: str) -> None:
        writes.append((path, content))

    monkeypatch.setattr(videos, "_atomic_write_text", atomic_write_spy)

    post_dir = write_post_payload(
        context,
        "SC4",
        "caption via atomic write",
        [
            {
                "media_id": "MID4",
                "shortcode": "SC4",
                "post_url": "https://www.instagram.com/p/SC4/",
                "id": "12",
                "created_at_utc": "2026-01-01T00:00:00Z",
                "text": "hello",
                "comment_like_count": "1",
                "owner_username": "bob",
                "owner_id": "456",
            },
        ],
    )

    metadata = post_metadata(
        post_target(
            shortcode="SC4",
            media_id="MID4",
            post_url="https://www.instagram.com/p/SC4/",
        ),
        "caption via atomic write",
        "1",
        1,
        [],
    )
    write_post_metadata(post_dir, metadata)

    write_paths = {path.name for path, _ in writes}
    assert write_paths == {"caption.txt", "comments.csv", "metadata.json"}
    comments_csv = next(
        content for path, content in writes if path.name == "comments.csv"
    )
    comments_rows = [line for line in comments_csv.splitlines() if line.strip()]
    assert comments_rows[0].startswith("media_id,shortcode,post_url,id")
    assert "MID4,SC4,https://www.instagram.com/p/SC4/,12" in comments_rows[1]


def test_process_post_row_media_info_failure_marks_completed_without_delay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module_dict = videos.__dict__
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
    prepare_output = module_dict["_prepare_output"]
    initial_metrics = module_dict["_initial_metrics"]
    download_context = module_dict["_DownloadContext"]
    process_post_row = module_dict["_process_post_row"]

    paths = prepare_output(cfg)
    context = download_context(
        cfg=cfg,
        session=object(),
        paths=paths,
        comments_by_shortcode={},
        metrics=initial_metrics(None),
        completed=set(),
    )

    def fake_fetch_media_info(session, media_id, inner_cfg):
        del session, media_id, inner_cfg
        return None, "media_info_request_failed"

    delay_calls = 0

    def fake_randomized_delay(inner_cfg, *, scale=1.0):
        del inner_cfg, scale
        nonlocal delay_calls
        delay_calls += 1

    monkeypatch.setattr(videos, "_fetch_media_info", fake_fetch_media_info)
    monkeypatch.setattr(videos, "_randomized_delay", fake_randomized_delay)

    row = {
        "shortcode": "SC3",
        "media_id": "MID3",
        "post_url": "https://www.instagram.com/p/SC3/",
        "caption": "ignored",
    }
    process_post_row(context, row)

    assert context.metrics["processed"] == 1
    assert context.metrics["errors"] == 1
    assert context.metrics["downloaded_files"] == 0
    assert delay_calls == 0
    assert "SC3" in context.completed

    error_rows = (cfg.output_dir / "videos_errors.csv").read_text(encoding="utf-8")
    assert "fetch_media_info" in error_rows
    assert "media_info_request_failed" in error_rows
    assert not (cfg.output_dir / "videos_checkpoint.json").exists()


def test_locked_path_uses_sidecar_lock_contract(tmp_path: Path) -> None:
    module = _shared_io_module()
    target = tmp_path / "nested" / "payload.ndjson"
    sidecar = target.with_suffix(".ndjson.lock")

    with module.__dict__["locked_path"](target):
        assert sidecar.exists()
        target.write_text("{}\n", encoding="utf-8")

    assert target.exists()


def test_atomic_and_append_helpers_create_parent_directories(tmp_path: Path) -> None:
    module = _shared_io_module()
    atomic_write_text = module.__dict__["atomic_write_text"]
    write_json_line = module.__dict__["write_json_line"]
    ensure_csv_with_header = module.__dict__["ensure_csv_with_header"]
    append_csv_row = module.__dict__["append_csv_row"]

    state_path = tmp_path / "deep" / "state" / "checkpoint.json"
    atomic_write_text(state_path, '{"processed": 1}')
    assert state_path.read_text(encoding="utf-8") == '{"processed": 1}'

    temp_candidates = list(state_path.parent.glob(f"{state_path.name}.*.tmp"))
    assert temp_candidates == []

    ndjson_path = tmp_path / "deep" / "events" / "rows.ndjson"
    write_json_line(ndjson_path, {"id": 1, "status": "ok"})
    ndjson_rows = [
        json.loads(line)
        for line in ndjson_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert ndjson_rows == [{"id": 1, "status": "ok"}]

    csv_path = tmp_path / "deep" / "tabular" / "rows.csv"
    header = ["id", "status"]
    ensure_csv_with_header(csv_path, header, reset=False)
    append_csv_row(csv_path, header, {"id": 2, "status": "saved"})
    csv_lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert csv_lines == ["id,status", "2,saved"]


def test_load_json_dict_handles_malformed_and_non_dict_payloads(tmp_path: Path) -> None:
    load_json_dict = _shared_io_module().__dict__["load_json_dict"]

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    assert load_json_dict(malformed) is None

    non_dict = tmp_path / "non_dict.json"
    non_dict.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_json_dict(non_dict) is None

    valid_dict = tmp_path / "valid_dict.json"
    valid_dict.write_text('{"ok": true}', encoding="utf-8")
    assert load_json_dict(valid_dict) == {"ok": True}

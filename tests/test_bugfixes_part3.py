import importlib
import json
from pathlib import Path

import pytest

from instagram_scraper.workflows import (
    _video_download_process as video_download_process,
)
from instagram_scraper.workflows import video_downloads as videos


def _shared_io_module():
    return importlib.import_module("instagram_scraper.infrastructure.files")


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
    assert write_paths == {"caption.txt", "metadata.json"}
    comments_csv = (post_dir / "comments.csv").read_text(encoding="utf-8")
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

    monkeypatch.setattr(
        video_download_process,
        "_fetch_media_info",
        fake_fetch_media_info,
    )
    monkeypatch.setattr(
        video_download_process,
        "_randomized_delay",
        fake_randomized_delay,
    )

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

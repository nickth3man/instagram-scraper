import json
from pathlib import Path

from instagram_scraper.pipeline import execute_pipeline
from instagram_scraper.storage_db import create_store


def test_execute_pipeline_writes_summary_and_targets(tmp_path: Path) -> None:
    output_dir = tmp_path / "cats"
    summary = execute_pipeline(
        "hashtag",
        hashtag="cats",
        limit=2,
        output_dir=output_dir,
        has_auth=True,
    )
    assert summary.output_dir == output_dir
    payload = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "hashtag"
    assert payload["targets"] == 2
    lines = (output_dir / "targets.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_execute_pipeline_initializes_standard_artifacts_and_state_store(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "followers"
    execute_pipeline(
        "followers",
        username="example",
        limit=2,
        output_dir=output_dir,
        has_auth=True,
    )
    for name in (
        "summary.json",
        "targets.ndjson",
        "users.ndjson",
        "posts.ndjson",
        "comments.ndjson",
        "stories.ndjson",
        "errors.ndjson",
    ):
        assert (output_dir / name).exists()
    store = create_store(output_dir / "state.sqlite3")
    assert store.count_targets() == 2


def test_profile_pipeline_writes_normalized_post_and_comment_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run_profile(*, username: str, output_dir: Path) -> dict[str, object]:
        dataset = {
            "target_profile": username,
            "posts": [
                {
                    "shortcode": "abc123",
                    "post_url": "https://www.instagram.com/p/abc123/",
                    "date_utc": "2026-03-05T12:00:00+00:00",
                    "caption": "hello",
                    "likes": 7,
                    "comments_count_reported": 1,
                    "is_video": False,
                    "typename": "GraphImage",
                    "owner_username": username,
                    "comments": [
                        {
                            "id": "c1",
                            "parent_id": None,
                            "created_at_utc": "2026-03-05T12:01:00+00:00",
                            "text": "nice",
                            "comment_like_count": 0,
                            "owner_username": "reader",
                            "owner_id": "99",
                            "post_shortcode": "abc123",
                        },
                    ],
                },
            ],
        }
        (output_dir / "instagram_dataset.json").write_text(
            json.dumps(dataset),
            encoding="utf-8",
        )
        return {"posts": 1, "comments": 1, "errors": 0}

    monkeypatch.setattr(
        "instagram_scraper.providers.profile.run_profile_scrape",
        fake_run_profile,
    )
    output_dir = tmp_path / "example"
    execute_pipeline("profile", username="example", output_dir=output_dir)
    posts_lines = (output_dir / "posts.ndjson").read_text(encoding="utf-8").splitlines()
    comments_lines = (output_dir / "comments.ndjson").read_text(
        encoding="utf-8",
    ).splitlines()
    assert len(posts_lines) == 1
    assert len(comments_lines) == 1


def test_profile_pipeline_records_raw_capture_manifest_when_enabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run_profile(*, username: str, output_dir: Path) -> dict[str, object]:
        payload = {"target_profile": username, "posts": []}
        (output_dir / "instagram_dataset.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        return {"posts": 0, "comments": 0, "errors": 0}

    monkeypatch.setattr(
        "instagram_scraper.providers.profile.run_profile_scrape",
        fake_run_profile,
    )
    output_dir = tmp_path / "example"
    execute_pipeline(
        "profile",
        username="example",
        output_dir=output_dir,
        raw_captures=True,
    )
    lines = (output_dir / "raw_captures.ndjson").read_text(
        encoding="utf-8",
    ).splitlines()
    assert len(lines) == 1

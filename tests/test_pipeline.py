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

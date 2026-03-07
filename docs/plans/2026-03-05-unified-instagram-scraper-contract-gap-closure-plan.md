# Unified Instagram Scraper Contract Gap Closure Implementation Plan

**Goal:** Close the remaining contract-level gaps between the approved unified-scraper design and the current scaffold by expanding the shared config and CLI surface, enriching normalized artifact ownership, and adapting legacy outputs into the unified artifact family.

**Architecture:** Keep the current provider-driven CLI and pipeline. Extend the typed config and command surface only where runtime semantics already exist, then make the pipeline own more of the normalized artifact contract by writing profile-derived normalized records and optional raw-capture metadata. Preserve the legacy scrapers as execution backends rather than rewriting them.

**Tech Stack:** Python 3.13, Typer, Pydantic, pytest, Rich, SQLAlchemy, structlog

---

### Task 1: Expand Shared Config and CLI Surface

**Files:**
- Modify: `src/instagram_scraper/config.py`
- Modify: `src/instagram_scraper/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli_commands.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from typer.testing import CliRunner

from instagram_scraper.cli import app
from instagram_scraper.config import AppConfig


def test_app_config_includes_shared_runtime_controls() -> None:
    config = AppConfig()
    assert config.raw_captures is False
    assert config.request_timeout == 30
    assert config.max_retries == 5
    assert config.min_delay == 0.05
    assert config.max_delay == 0.2
    assert config.checkpoint_every == 20


def test_url_subcommand_passes_runtime_controls(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(
        app,
        [
            "scrape",
            "url",
            "--url",
            "https://www.instagram.com/p/example/",
            "--raw-captures",
            "--request-timeout",
            "15",
            "--max-retries",
            "2",
            "--min-delay",
            "0.1",
            "--max-delay",
            "0.3",
            "--checkpoint-every",
            "7",
        ],
    )
    assert result.exit_code == 0
    assert called["mode"] == "url"
    kwargs = called["kwargs"]
    assert kwargs["raw_captures"] is True
    assert kwargs["request_timeout"] == 15
    assert kwargs["max_retries"] == 2
    assert kwargs["min_delay"] == 0.1
    assert kwargs["max_delay"] == 0.3
    assert kwargs["checkpoint_every"] == 7
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_config.py tests/test_cli_commands.py::test_url_subcommand_passes_runtime_controls -v`
Expected: FAIL because the config model and CLI do not yet expose the full shared runtime controls.

**Step 3: Write minimal implementation**

```python
class AppConfig(BaseModel):
    output_dir: Path = Path("data")
    limit: int | None = Field(default=None, ge=1)
    raw_captures: bool = False
    request_timeout: int = Field(default=30, ge=1)
    max_retries: int = Field(default=5, ge=1)
    min_delay: float = Field(default=0.05, ge=0)
    max_delay: float = Field(default=0.2, ge=0)
    checkpoint_every: int = Field(default=20, ge=1)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_config.py tests/test_cli_commands.py::test_url_subcommand_passes_runtime_controls -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/config.py src/instagram_scraper/cli.py tests/test_config.py tests/test_cli_commands.py
git commit -m "feat: add shared unified runtime controls"
```

### Task 2: Normalize Legacy Profile Outputs Into Unified Artifacts

**Files:**
- Modify: `src/instagram_scraper/pipeline.py`
- Modify: `src/instagram_scraper/providers/profile.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
import json
from pathlib import Path

from instagram_scraper.pipeline import execute_pipeline


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
    comments_lines = (output_dir / "comments.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(posts_lines) == 1
    assert len(comments_lines) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_pipeline.py::test_profile_pipeline_writes_normalized_post_and_comment_artifacts -v`
Expected: FAIL because the unified pipeline does not yet adapt legacy profile output into normalized NDJSON artifacts.

**Step 3: Write minimal implementation**

```python
def _populate_profile_artifacts(output_dir: Path) -> None:
    dataset_path = output_dir / "instagram_dataset.json"
    if not dataset_path.exists():
        return
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_pipeline.py::test_profile_pipeline_writes_normalized_post_and_comment_artifacts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/pipeline.py src/instagram_scraper/providers/profile.py tests/test_pipeline.py
git commit -m "feat: normalize legacy profile artifacts"
```

### Task 3: Add Optional Raw-Capture Manifest Support

**Files:**
- Modify: `src/instagram_scraper/pipeline.py`
- Modify: `src/instagram_scraper/models.py`
- Modify: `src/instagram_scraper/cli.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
import json
from pathlib import Path

from instagram_scraper.pipeline import execute_pipeline


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
    lines = (output_dir / "raw_captures.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_pipeline.py::test_profile_pipeline_records_raw_capture_manifest_when_enabled -v`
Expected: FAIL because raw-capture manifest support is not yet implemented.

**Step 3: Write minimal implementation**

```python
if raw_captures and dataset_path.exists():
    write_json_line(
        output_dir / "raw_captures.ndjson",
        RawCaptureRecord(
            provider="instaloader",
            target=f"profile:{username}",
            path=dataset_path,
        ).model_dump(mode="json"),
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_pipeline.py::test_profile_pipeline_records_raw_capture_manifest_when_enabled -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/pipeline.py src/instagram_scraper/models.py src/instagram_scraper/cli.py tests/test_pipeline.py
git commit -m "feat: add raw capture manifest support"
```

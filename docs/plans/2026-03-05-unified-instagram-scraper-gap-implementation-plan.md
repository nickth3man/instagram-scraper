# Unified Instagram Scraper Gap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the major gaps between the approved unified-scraper design and the current scaffolded implementation by expanding the CLI surface, wiring a real normalized pipeline, and wrapping legacy profile and browser-dump flows through the unified command graph.

**Architecture:** Keep the codebase HTTP-first and provider-driven, but move the pipeline from placeholder summaries to a real run orchestration layer. The unified pipeline will own support-tier preflight, target resolution, artifact initialization, support-state storage, summary rendering, and legacy-wrapper execution boundaries.

**Tech Stack:** Python 3.13, Typer, Pydantic, SQLAlchemy, Rich, structlog, diskcache, pytest, Ruff, Ty

---

### Task 1: Expand the CLI Surface to Match the Design

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_cli_app.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_cli_commands.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_scrape_help_lists_all_unified_modes() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    for command in (
        "profile",
        "url",
        "urls",
        "hashtag",
        "location",
        "followers",
        "following",
        "likers",
        "commenters",
        "stories",
    ):
        assert command in result.stdout


def test_urls_subcommand_invokes_pipeline(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    called: dict[str, object] = {}

    def fake_run(mode: str, **kwargs: object) -> int:
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    input_path = tmp_path / "urls.txt"
    input_path.write_text("https://www.instagram.com/p/example/\n", encoding="utf-8")
    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(app, ["scrape", "urls", "--input", str(input_path)])
    assert result.exit_code == 0
    assert called["mode"] == "urls"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_cli_app.py tests/test_cli_commands.py -v`
Expected: FAIL because the unified command tree does not expose `urls`, and several designed subcommands still miss the expected seed options.

**Step 3: Write minimal implementation**

```python
@scrape_app.command("urls")
def scrape_urls(
    input_path: Path = typer.Option(..., "--input"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    cookie_header: str = typer.Option("", "--cookie-header"),
) -> None:
    raise typer.Exit(
        run_pipeline(
            "urls",
            input_path=input_path,
            output_dir=output_dir,
            cookie_header=cookie_header,
            has_auth=bool(cookie_header),
        ),
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_cli_app.py tests/test_cli_commands.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/cli.py tests/test_cli_app.py tests/test_cli_commands.py
git commit -m "feat: expand unified scrape cli surface"
```

### Task 2: Expand the Normalized Models and Capability Metadata

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/models.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/capabilities.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_models.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_capabilities.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.capabilities import describe_mode_capability
from instagram_scraper.models import ErrorRecord, RawCaptureRecord, StoryRecord, UserRecord


def test_mode_capability_marks_profile_stable() -> None:
    descriptor = describe_mode_capability("profile")
    assert descriptor.support_tier == "stable"
    assert descriptor.requires_auth is False


def test_additional_record_families_are_available() -> None:
    user = UserRecord(provider="http", target_kind="user", username="example")
    story = StoryRecord(
        provider="http",
        target_kind="story",
        story_id="story-1",
        owner_username="example",
    )
    error = ErrorRecord(
        provider="http",
        stage="resolve",
        target="profile:example",
        error_code="boom",
    )
    raw = RawCaptureRecord(
        provider="http",
        target="profile:example",
        path="data/example/raw/payload.json",
    )
    assert user.username == "example"
    assert story.story_id == "story-1"
    assert error.error_code == "boom"
    assert str(raw.path).endswith("payload.json")
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_models.py tests/test_capabilities.py -v`
Expected: FAIL because the normalized record family is incomplete and capability metadata does not yet expose support tiers.

**Step 3: Write minimal implementation**

```python
SUPPORT_TIER_BY_MODE = {
    "profile": "stable",
    "url": "stable",
    "urls": "stable",
    "hashtag": "auth-required",
    "location": "auth-required",
    "stories": "auth-required",
    "followers": "experimental",
    "following": "experimental",
    "likers": "experimental",
    "commenters": "experimental",
}
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_models.py tests/test_capabilities.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/models.py src/instagram_scraper/capabilities.py tests/test_models.py tests/test_capabilities.py
git commit -m "feat: expand normalized records and mode metadata"
```

### Task 3: Turn the Pipeline Into a Real Artifact-Oriented Run Orchestrator

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/pipeline.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/base.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/hashtag.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/location.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/follow_graph.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/interactions.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/stories.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_presentation.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_storage_db.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_shared_io.py`
- Add: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
import json

from instagram_scraper.pipeline import execute_pipeline


def test_execute_pipeline_writes_summary_and_targets(tmp_path) -> None:
    summary = execute_pipeline(
        "hashtag",
        hashtag="cats",
        limit=2,
        output_dir=tmp_path / "cats",
        has_auth=True,
    )
    assert summary.output_dir == tmp_path / "cats"
    payload = json.loads((tmp_path / "cats" / "summary.json").read_text(encoding="utf-8"))
    assert payload["mode"] == "hashtag"
    lines = (tmp_path / "cats" / "targets.ndjson").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_pipeline.py -v`
Expected: FAIL because the pipeline does not yet initialize normalized artifacts, persist targets, or write summary files.

**Step 3: Write minimal implementation**

```python
def execute_pipeline(mode: str, **kwargs: object) -> RunSummary:
    output_dir = _resolve_output_dir(mode, kwargs)
    paths = _initialize_artifacts(output_dir)
    targets = _resolve_targets(mode, kwargs)
    _write_targets(paths["targets"], targets)
    summary = _run_mode(mode, kwargs | {"output_dir": output_dir})
    _write_summary(output_dir, summary)
    return summary
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_pipeline.py tests/test_storage_db.py tests/test_shared_io.py tests/test_presentation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/pipeline.py src/instagram_scraper/providers/base.py src/instagram_scraper/providers/hashtag.py src/instagram_scraper/providers/location.py src/instagram_scraper/providers/follow_graph.py src/instagram_scraper/providers/interactions.py src/instagram_scraper/providers/stories.py tests/test_pipeline.py tests/test_storage_db.py tests/test_shared_io.py tests/test_presentation.py
git commit -m "feat: add normalized unified pipeline artifacts"
```

### Task 4: Wrap Legacy Profile and Browser-Dump Flows Through the Unified Providers

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/scrape_instagram_profile.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/scrape_instagram_from_browser_dump.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/profile.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/providers/url.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/cli.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/README.md`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/docs/README.md`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_providers_profile.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_providers_url.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_entrypoint.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from instagram_scraper.providers.profile import ProfileScrapeProvider
from instagram_scraper.providers.url import UrlScrapeProvider


def test_profile_provider_delegates_to_legacy_runner(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    def fake_run_profile(*, username: str, output_dir: Path) -> dict[str, object]:
        called["username"] = username
        called["output_dir"] = output_dir
        return {"posts": 3, "comments": 4, "errors": 0}

    monkeypatch.setattr(
        "instagram_scraper.providers.profile.run_profile_scrape",
        fake_run_profile,
    )
    summary = ProfileScrapeProvider.run(username="example", output_dir=tmp_path)
    assert summary.posts == 3
    assert called["output_dir"] == tmp_path


def test_url_provider_delegates_to_browser_dump_runner(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    def fake_run_urls(*, urls: list[str], output_dir: Path, cookie_header: str) -> dict[str, object]:
        called["urls"] = urls
        called["output_dir"] = output_dir
        called["cookie_header"] = cookie_header
        return {"posts": 1, "comments": 2, "errors": 0}

    monkeypatch.setattr("instagram_scraper.providers.url.run_url_scrape", fake_run_urls)
    summary = UrlScrapeProvider.run(
        post_url="https://www.instagram.com/p/example/",
        output_dir=tmp_path,
        cookie_header="sessionid=abc",
    )
    assert summary.posts == 1
    assert called["urls"] == ["https://www.instagram.com/p/example/"]
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_providers_profile.py tests/test_providers_url.py tests/test_entrypoint.py -v`
Expected: FAIL because the providers still return placeholders instead of delegating into the legacy scrapers.

**Step 3: Write minimal implementation**

```python
def run_profile_scrape(*, username: str, output_dir: Path) -> dict[str, object]:
    ...


def run_url_scrape(*, urls: list[str], output_dir: Path, cookie_header: str) -> dict[str, object]:
    ...
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_providers_profile.py tests/test_providers_url.py tests/test_entrypoint.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/scrape_instagram_profile.py src/instagram_scraper/scrape_instagram_from_browser_dump.py src/instagram_scraper/providers/profile.py src/instagram_scraper/providers/url.py src/instagram_scraper/cli.py README.md docs/README.md tests/test_providers_profile.py tests/test_providers_url.py tests/test_entrypoint.py
git commit -m "feat: wrap legacy scrapers through unified providers"
```

### Final Verification

Run:

```bash
uv run ruff check .
uv run ty check
uv run python -m pytest
```

Expected:

- Ruff passes with no violations.
- Ty passes with no warnings or errors.
- Full test suite passes.

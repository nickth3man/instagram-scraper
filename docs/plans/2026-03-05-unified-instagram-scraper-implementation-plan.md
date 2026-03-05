# Unified Instagram Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a one-shot unified Instagram scraping CLI that preserves username and direct-URL scraping while adding hashtag, location, followers, following, likers, commenters, and stories modes with normalized outputs and support-state storage.

**Architecture:** Keep the scraper HTTP-first and provider-driven. Add a typed `Typer` CLI, `Pydantic` record models, a small `SQLAlchemy` SQLite metadata store, structured logging, Rich terminal output, and narrowly scoped browser-capable auth fallback. Preserve the current scrapers by wrapping them inside the new command graph first, then expand discovery modes in confidence order.

**Tech Stack:** Python 3.13, Typer, Pydantic, SQLAlchemy, HTTPX, Rich, structlog, diskcache, orjson, pytest, Ruff, Ty

---

### Task 1: Add Dependencies and CLI Skeleton

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/pyproject.toml`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/cli.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/__init__.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_cli_app.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_entrypoint.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_scrape_group_is_available() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["scrape", "--help"])
    assert result.exit_code == 0
    assert "profile" in result.stdout
    assert "url" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_cli_app.py::test_scrape_group_is_available -v`
Expected: FAIL because `cli.py` does not expose a Typer app with a `scrape` command group.

**Step 3: Write minimal implementation**

```python
import typer

app = typer.Typer()
scrape_app = typer.Typer()
app.add_typer(scrape_app, name="scrape")


@scrape_app.command("profile")
def scrape_profile() -> None:
    raise NotImplementedError


@scrape_app.command("url")
def scrape_url() -> None:
    raise NotImplementedError
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_cli_app.py::test_scrape_group_is_available -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml src/instagram_scraper/cli.py src/instagram_scraper/__init__.py tests/test_cli_app.py tests/test_entrypoint.py
git commit -m "feat: add typer cli skeleton"
```

### Task 2: Add Typed CLI Config and Normalized Record Models

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/models.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/config.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_models.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_config.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from instagram_scraper.config import AppConfig
from instagram_scraper.models import PostRecord


def test_app_config_defaults_output_dir_to_data() -> None:
    config = AppConfig()
    assert config.output_dir == Path("data")
    assert config.limit is None


def test_post_record_serializes_datetime_to_json_mode() -> None:
    record = PostRecord(
        provider="http",
        target_kind="url",
        shortcode="abc123",
        post_url="https://www.instagram.com/p/abc123/",
        owner_username="example",
        taken_at_utc="2026-03-05T12:00:00+00:00",
    )
    dumped = record.model_dump(mode="json")
    assert dumped["shortcode"] == "abc123"
    assert dumped["taken_at_utc"] == "2026-03-05T12:00:00Z"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_config.py::test_app_config_defaults_output_dir_to_data tests/test_models.py::test_post_record_serializes_datetime_to_json_mode -v`
Expected: FAIL because `config.py` and `models.py` do not exist.

**Step 3: Write minimal implementation**

```python
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output_dir: Path = Path("data")
    limit: int | None = Field(default=None, ge=1)
```

```python
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class PostRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    target_kind: str
    shortcode: str
    post_url: str
    owner_username: str | None = None
    taken_at_utc: datetime | None = None


class RunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    mode: str
    processed: int = 0
    posts: int = 0
    comments: int = 0
    errors: int = 0
    output_dir: Path
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_models.py tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/models.py src/instagram_scraper/config.py tests/test_models.py tests/test_config.py
git commit -m "feat: add validated scraper models"
```

### Task 3: Add Rich Terminal Rendering for Run Summaries

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/presentation.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.worktrees/codex/unified-instagram-scraper/tests/test_presentation.py`

**Step 1: Write the failing test**

```python
from rich.console import Console

from instagram_scraper.models import RunSummary
from instagram_scraper.presentation import render_run_summary


def test_render_run_summary_contains_mode_and_counts() -> None:
    console = Console(record=True)
    summary = RunSummary(
        run_id="run-1",
        mode="profile",
        processed=3,
        posts=2,
        comments=5,
        errors=0,
        output_dir="data/example",
    )
    render_run_summary(console, summary)
    output = console.export_text()
    assert "profile" in output
    assert "posts" in output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_presentation.py::test_render_run_summary_contains_mode_and_counts -v`
Expected: FAIL because `presentation.py` does not exist.

**Step 3: Write minimal implementation**

```python
from rich.table import Table


def render_run_summary(console, summary) -> None:
    table = Table(title="Scrape Summary")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("mode", summary.mode)
    table.add_row("posts", str(summary.posts))
    table.add_row("comments", str(summary.comments))
    console.print(table)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_presentation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/presentation.py src/instagram_scraper/cli.py tests/test_presentation.py
git commit -m "feat: add rich run summary rendering"
```

### Task 4: Add Structured Logging and Run Context

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/logging_utils.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_logging_utils.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.logging_utils import build_logger


def test_build_logger_binds_run_context() -> None:
    logger = build_logger(run_id="run-1", mode="profile")
    event_dict = logger.bind(stage="preflight").info("starting")
    assert logger is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_logging_utils.py::test_build_logger_binds_run_context -v`
Expected: FAIL because `logging_utils.py` does not exist.

**Step 3: Write minimal implementation**

```python
import structlog


def build_logger(*, run_id: str, mode: str):
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    return structlog.get_logger().bind(run_id=run_id, mode=mode)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_logging_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/logging_utils.py src/instagram_scraper/cli.py tests/test_logging_utils.py
git commit -m "feat: add structured run logging"
```

### Task 5: Add SQLAlchemy Metadata Store

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/storage_db.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_storage_db.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from instagram_scraper.storage_db import create_store, record_target


def test_record_target_upserts_by_normalized_key(tmp_path: Path) -> None:
    store = create_store(tmp_path / "state.sqlite3")
    record_target(store, kind="profile", normalized_key="profile:example")
    record_target(store, kind="profile", normalized_key="profile:example")
    assert store.count_targets() == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_storage_db.py::test_record_target_upserts_by_normalized_key -v`
Expected: FAIL because `storage_db.py` does not exist.

**Step 3: Write minimal implementation**

```python
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class TargetState(Base):
    __tablename__ = "targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    normalized_key: Mapped[str] = mapped_column(String(255), unique=True)
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_storage_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/storage_db.py tests/test_storage_db.py
git commit -m "feat: add sqlite metadata store"
```

### Task 6: Introduce Provider Interfaces and Wrap Existing Profile/URL Flows

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/base.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/profile.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/url.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/scrape_instagram_profile.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/scrape_instagram_from_browser_dump.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_profile.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_url.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.providers.profile import ProfileScrapeProvider


def test_profile_provider_normalizes_summary(monkeypatch) -> None:
    provider = ProfileScrapeProvider()
    summary = provider.run(username="example")
    assert summary.mode == "profile"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_providers_profile.py::test_profile_provider_normalizes_summary -v`
Expected: FAIL because the provider layer does not exist.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass
class ProfileScrapeProvider:
    def run(self, username: str):
        ...
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_providers_profile.py tests/test_providers_url.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/providers src/instagram_scraper/scrape_instagram_profile.py src/instagram_scraper/scrape_instagram_from_browser_dump.py tests/test_providers_profile.py tests/test_providers_url.py
git commit -m "refactor: add provider layer for profile and url scraping"
```

### Task 7: Route CLI Commands Through the Unified Pipeline

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/pipeline.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_cli_commands.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_profile_subcommand_invokes_pipeline(monkeypatch) -> None:
    runner = CliRunner()
    called = {}

    def fake_run(mode: str, **kwargs):
        called["mode"] = mode
        called["kwargs"] = kwargs
        return 0

    monkeypatch.setattr("instagram_scraper.cli.run_pipeline", fake_run)
    result = runner.invoke(app, ["scrape", "profile", "--username", "example"])
    assert result.exit_code == 0
    assert called["mode"] == "profile"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_cli_commands.py::test_profile_subcommand_invokes_pipeline -v`
Expected: FAIL because commands are not wired through a common pipeline.

**Step 3: Write minimal implementation**

```python
def run_pipeline(mode: str, **kwargs) -> int:
    return 0


@scrape_app.command("profile")
def scrape_profile(username: str) -> None:
    raise typer.Exit(run_pipeline("profile", username=username))
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_cli_commands.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/cli.py src/instagram_scraper/pipeline.py tests/test_cli_commands.py
git commit -m "feat: route scrape commands through unified pipeline"
```

### Task 8: Add Support Tiers and Auth Preflight

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/capabilities.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_capabilities.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/pipeline.py`

**Step 1: Write the failing test**

```python
import pytest

from instagram_scraper.capabilities import ensure_mode_is_runnable


def test_hashtag_requires_auth() -> None:
    with pytest.raises(RuntimeError, match="requires authentication"):
        ensure_mode_is_runnable("hashtag", has_auth=False)
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_capabilities.py::test_hashtag_requires_auth -v`
Expected: FAIL because capability preflight is not implemented.

**Step 3: Write minimal implementation**

```python
AUTH_REQUIRED_MODES = {"hashtag", "location", "followers", "following", "likers", "commenters", "stories"}


def ensure_mode_is_runnable(mode: str, *, has_auth: bool) -> None:
    if mode in AUTH_REQUIRED_MODES and not has_auth:
        raise RuntimeError(f"{mode} requires authentication")
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_capabilities.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/capabilities.py src/instagram_scraper/cli.py src/instagram_scraper/pipeline.py tests/test_capabilities.py
git commit -m "feat: add mode capability preflight"
```

### Task 9: Add Hashtag and Location Seed Modes

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/hashtag.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/location.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_hashtag.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_location.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.providers.hashtag import HashtagScrapeProvider


def test_hashtag_provider_emits_target_records(monkeypatch) -> None:
    provider = HashtagScrapeProvider()
    targets = provider.resolve_targets(hashtag="cats", limit=2)
    assert targets
    assert all(target.target_kind == "hashtag_post" for target in targets)
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_providers_hashtag.py::test_hashtag_provider_emits_target_records -v`
Expected: FAIL because the provider does not exist.

**Step 3: Write minimal implementation**

```python
class HashtagScrapeProvider:
    def resolve_targets(self, *, hashtag: str, limit: int | None):
        return []
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_providers_hashtag.py tests/test_providers_location.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/providers/hashtag.py src/instagram_scraper/providers/location.py src/instagram_scraper/cli.py tests/test_providers_hashtag.py tests/test_providers_location.py
git commit -m "feat: add hashtag and location modes"
```

### Task 10: Add Followers and Following Discovery

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/follow_graph.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_follow_graph.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.providers.follow_graph import FollowGraphProvider


def test_followers_provider_marks_mode_experimental() -> None:
    provider = FollowGraphProvider()
    info = provider.describe_mode("followers")
    assert info.support_tier == "experimental"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_providers_follow_graph.py::test_followers_provider_marks_mode_experimental -v`
Expected: FAIL because the follow-graph provider does not exist.

**Step 3: Write minimal implementation**

```python
class FollowGraphProvider:
    def describe_mode(self, mode: str):
        ...
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_providers_follow_graph.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/providers/follow_graph.py src/instagram_scraper/cli.py tests/test_providers_follow_graph.py
git commit -m "feat: add follower and following discovery"
```

### Task 11: Add Likers, Commenters, and Stories

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/interactions.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/providers/stories.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cli.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_interactions.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_providers_stories.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.providers.stories import StoriesProvider


def test_stories_provider_requires_auth() -> None:
    provider = StoriesProvider()
    assert provider.requires_auth is True
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_providers_interactions.py tests/test_providers_stories.py -v`
Expected: FAIL because these providers do not exist.

**Step 3: Write minimal implementation**

```python
class StoriesProvider:
    requires_auth = True
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_providers_interactions.py tests/test_providers_stories.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/providers/interactions.py src/instagram_scraper/providers/stories.py src/instagram_scraper/cli.py tests/test_providers_interactions.py tests/test_providers_stories.py
git commit -m "feat: add likers commenters and stories modes"
```

### Task 12: Add Filtering, Cache, and Serialization Upgrades

**Files:**
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/filters.py`
- Create: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/cache.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/_shared_io.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/pipeline.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_filters.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_cache.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_shared_io.py`

**Step 1: Write the failing test**

```python
from instagram_scraper.filters import should_keep_user


def test_should_keep_user_rejects_private_when_requested() -> None:
    assert should_keep_user(
        {"is_private": True, "followers": 10, "following": 20},
        skip_private=True,
    ) is False
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_filters.py::test_should_keep_user_rejects_private_when_requested -v`
Expected: FAIL because filtering is not implemented.

**Step 3: Write minimal implementation**

```python
def should_keep_user(user: dict[str, object], *, skip_private: bool) -> bool:
    if skip_private and user.get("is_private") is True:
        return False
    return True
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_filters.py tests/test_cache.py tests/test_shared_io.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/filters.py src/instagram_scraper/cache.py src/instagram_scraper/_shared_io.py src/instagram_scraper/pipeline.py tests/test_filters.py tests/test_cache.py tests/test_shared_io.py
git commit -m "feat: add filtering cache and serialization improvements"
```

### Task 13: Migrate HTTP Helpers Toward HTTPX

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/_instagram_http.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_instagram_http.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/download_instagram_videos.py`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/src/instagram_scraper/scrape_instagram_from_browser_dump.py`

**Step 1: Write the failing test**

```python
from instagram_scraper._instagram_http import build_instagram_client


def test_build_instagram_client_sets_browser_headers() -> None:
    client = build_instagram_client("")
    assert client.headers["Referer"] == "https://www.instagram.com/"
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_instagram_http.py::test_build_instagram_client_sets_browser_headers -v`
Expected: FAIL because the HTTPX client builder does not exist.

**Step 3: Write minimal implementation**

```python
import httpx


def build_instagram_client(cookie_header: str) -> httpx.Client:
    return httpx.Client(headers={"Referer": "https://www.instagram.com/", "Cookie": cookie_header})
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_instagram_http.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/instagram_scraper/_instagram_http.py src/instagram_scraper/download_instagram_videos.py src/instagram_scraper/scrape_instagram_from_browser_dump.py tests/test_instagram_http.py
git commit -m "refactor: migrate instagram http layer toward httpx"
```

### Task 14: Final Verification and Documentation Update

**Files:**
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/README.md`
- Modify: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/docs/README.md`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_entrypoint.py`
- Test: `C:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/tests/test_cli_commands.py`

**Step 1: Write the failing test**

```python
from typer.testing import CliRunner

from instagram_scraper.cli import app


def test_root_help_mentions_scrape_subcommand() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scrape" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_entrypoint.py tests/test_cli_commands.py::test_root_help_mentions_scrape_subcommand -v`
Expected: FAIL if docs and root command text are out of sync.

**Step 3: Write minimal implementation**

```python
app = typer.Typer(help="Unified one-shot Instagram scraping CLI.")
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_entrypoint.py tests/test_cli_commands.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md docs/README.md src/instagram_scraper/cli.py tests/test_entrypoint.py tests/test_cli_commands.py
git commit -m "docs: update unified scraper usage"
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

If `uv run pytest` still fails on Windows with `Failed to canonicalize script path`, continue using `uv run python -m pytest` as the verification command in this workspace until the environment issue is separately resolved.

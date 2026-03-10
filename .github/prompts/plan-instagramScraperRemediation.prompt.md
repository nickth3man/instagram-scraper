## Ready-to-apply patch

### `README.md` and `.gitignore`

```diff
diff --git a/README.md b/README.md
index 7c4d9f3..4b3b9c1 100644
--- a/README.md
+++ b/README.md
@@ -10,6 +10,30 @@ Unified one-shot Instagram scraping CLI with profile, URL, hashtag, location,
 ```bash
 uv sync
 ```
+
+## Authentication
+
+Some modes require Instagram cookies, including `hashtag`, `location`,
+`followers`, `following`, `likers`, `commenters`, `stories`,
+`sync hashtag`, and `sync location`.
+
+Prefer setting `IG_COOKIE_HEADER` in your shell or a project-local `.env`
+file. The CLI and downloader load `.env` from the repository root
+automatically.
+
+```bash
+# .env
+IG_COOKIE_HEADER=sessionid=...
+```
+
+```bash
+# bash
+export IG_COOKIE_HEADER='sessionid=...'
+```
+
+```powershell
+# PowerShell
+$env:IG_COOKIE_HEADER = 'sessionid=...'
+```
 
 ## Run
 
@@ -19,17 +43,21 @@ Run the package entrypoint:
 
 Run unified scrape modes:
 
 ```bash
 uv run instagram-scraper scrape profile --username example
 uv run instagram-scraper scrape url --url https://www.instagram.com/p/example/
 uv run instagram-scraper scrape urls --input data/tool_dump.json
-uv run instagram-scraper scrape hashtag --hashtag cats --cookie-header "sessionid=..."
-uv run instagram-scraper scrape location --location nyc --cookie-header "sessionid=..."
-uv run instagram-scraper scrape followers --username example --cookie-header "sessionid=..."
-uv run instagram-scraper scrape stories --username example --cookie-header "sessionid=..."
+uv run instagram-scraper scrape hashtag --hashtag cats
+uv run instagram-scraper scrape location --location nyc
+uv run instagram-scraper scrape followers --username example
+uv run instagram-scraper scrape stories --username example
+uv run instagram-scraper sync hashtag --hashtag cats
+uv run instagram-scraper sync location --location nyc
 ```
+
+You can still use `--cookie-header` for one-off commands, but environment-based
+auth keeps secrets out of shell history and matches the repository defaults.
 
 Shared options implemented today:
 
 ```bash
 --output-dir
 --limit
- --cookie-header
+--cookie-header  # optional override; prefer IG_COOKIE_HEADER or .env
 ```
 
 Additional mode-specific support:
diff --git a/.gitignore b/.gitignore
index 6fdb0fc..3ed6ec2 100644
--- a/.gitignore
+++ b/.gitignore
@@ -12,4 +12,3 @@ data/
 Thumbs.db
 .idea/
 .vscode/
-.env
```

### `tests/test_download_instagram_videos.py`

```diff
diff --git a/tests/test_download_instagram_videos.py b/tests/test_download_instagram_videos.py
index 3a1dc61..e8f4a51 100644
--- a/tests/test_download_instagram_videos.py
+++ b/tests/test_download_instagram_videos.py
@@ -566,6 +566,43 @@ def test_iter_target_rows_stops_early_with_low_limit(tmp_path: Path) -> None:
 
     assert [row["shortcode"] for row in rows] == ["VID001", "VID002"]
 
 
+def test_iter_target_rows_handles_large_synthetic_fixture(tmp_path: Path) -> None:
+    """Test larger synthetic inputs still yield videos first and stop at limit."""
+    csv_path = tmp_path / "posts.csv"
+    with csv_path.open("w", newline="", encoding="utf-8") as f:
+        writer = csv.writer(f)
+        writer.writerow(["shortcode", "media_id", "post_url", "type", "caption"])
+        for index in range(250):
+            writer.writerow(
+                [
+                    f"IMG{index:04d}",
+                    f"img-{index}",
+                    f"https://instagr.am/p/IMG{index:04d}",
+                    "1",
+                    f"Image {index}",
+                ],
+            )
+            writer.writerow(
+                [
+                    f"VID{index:04d}",
+                    f"vid-{index}",
+                    f"https://instagr.am/p/VID{index:04d}",
+                    str(MEDIA_TYPE_VIDEO),
+                    f"Video {index}",
+                ],
+            )
+            writer.writerow(
+                [
+                    f"CAR{index:04d}",
+                    f"car-{index}",
+                    f"https://instagr.am/p/CAR{index:04d}",
+                    str(MEDIA_TYPE_CAROUSEL),
+                    f"Carousel {index}",
+                ],
+            )
+
+    rows = list(iter_target_rows(csv_path, limit=7))
+
+    assert [row["shortcode"] for row in rows] == [f"VID{index:04d}" for index in range(7)]
+    assert {row["type"] for row in rows} == {str(MEDIA_TYPE_VIDEO)}
+
+
 def test_target_rows_empty_csv(tmp_path: Path) -> None:
     """Test handling empty CSV."""
     csv_path = tmp_path / "posts.csv"
@@ -759,6 +796,45 @@ def test_comments_lookup_builds_disk_backed_index(
     assert not index_path.exists()
 
 
+def test_comments_lookup_handles_large_synthetic_fixture(tmp_path: Path) -> None:
+    """Test disk-backed lookup returns expected rows for larger fixtures."""
+    csv_path = tmp_path / "comments.csv"
+    with csv_path.open("w", newline="", encoding="utf-8") as f:
+        writer = csv.writer(f)
+        writer.writerow(
+            [
+                "media_id",
+                "shortcode",
+                "post_url",
+                "id",
+                "created_at_utc",
+                "text",
+                "comment_like_count",
+                "owner_username",
+                "owner_id",
+            ],
+        )
+        for shortcode_index in range(40):
+            shortcode = f"POST{shortcode_index:03d}"
+            for comment_index in range(25):
+                writer.writerow(
+                    [
+                        f"media-{shortcode_index}",
+                        shortcode,
+                        f"https://www.instagram.com/p/{shortcode}/",
+                        f"{shortcode_index}-{comment_index}",
+                        "2024-01-15T10:00:00+00:00",
+                        f"Comment {shortcode_index:03d}-{comment_index:02d}",
+                        str(comment_index),
+                        f"user{comment_index:02d}",
+                        f"owner-{comment_index:02d}",
+                    ],
+                )
+
+    index_path = tmp_path / ".comments.sqlite3"
+    lookup = CommentsLookup(csv_path, index_path)
+    try:
+        rows = lookup.get("POST007")
+        assert len(rows) == 25
+        assert rows[0]["text"] == "Comment 007-00"
+        assert rows[-1]["text"] == "Comment 007-24"
+    finally:
+        lookup.close()
+
+    assert not index_path.exists()
+
+
 def test_download_session_pool_is_thread_local() -> None:
     """Test downloader sessions are isolated per worker thread."""
     first_session = MagicMock()
@@ -1392,6 +1468,108 @@ def test_run_with_resume(
     # Should skip the already completed post
     assert summary["processed"] == 1
 
 
+@patch("instagram_scraper.workflows.video_downloads._build_session")
+@patch("instagram_scraper.workflows.video_downloads._fetch_media_info")
+def test_run_with_resume_processes_new_posts_from_modified_input(
+    mock_fetch: MagicMock,
+    mock_build_session: MagicMock,
+    mock_session: MagicMock,
+    tmp_path: Path,
+) -> None:
+    """Test resume mode skips completed posts and processes newly added rows."""
+    posts_csv = tmp_path / "posts.csv"
+    with posts_csv.open("w", newline="", encoding="utf-8") as f:
+        writer = csv.writer(f)
+        writer.writerow(
+            [
+                "shortcode",
+                "media_id",
+                "post_url",
+                "type",
+                "caption",
+                "comment_count",
+            ],
+        )
+        writer.writerow(
+            [
+                "ABC123",
+                "1234567890",
+                "https://www.instagram.com/p/ABC123/",
+                str(MEDIA_TYPE_VIDEO),
+                "Already completed",
+                "1",
+            ],
+        )
+        writer.writerow(
+            [
+                "NEW456",
+                "9999999999",
+                "https://www.instagram.com/p/NEW456/",
+                str(MEDIA_TYPE_VIDEO),
+                "New post after checkpoint",
+                "2",
+            ],
+        )
+
+    checkpoint = {
+        "completed_shortcodes": ["ABC123"],
+        "processed": 1,
+        "downloaded_files": 1,
+        "errors": 0,
+        "skipped_no_video": 0,
+    }
+    (tmp_path / "videos_checkpoint.json").write_text(json.dumps(checkpoint))
+
+    config = Config(
+        output_dir=tmp_path,
+        posts_csv=posts_csv,
+        comments_csv=tmp_path / "comments.csv",
+        should_resume=True,
+        should_reset_output=False,
+        min_delay=0.01,
+        max_delay=0.02,
+        max_retries=3,
+        timeout=30,
+        checkpoint_every=10,
+        limit=None,
+        cookie_header="",
+        max_concurrent_downloads=2,
+    )
+    mock_build_session.return_value = mock_session
+    mock_fetch.return_value = (
+        {
+            "media_type": MEDIA_TYPE_VIDEO,
+            "video_versions": [
+                {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
+            ],
+        },
+        None,
+    )
+
+    def mock_download_side_effect(session, video_url, destination, cfg):
+        destination.parent.mkdir(parents=True, exist_ok=True)
+        destination.write_bytes(b"mock video content")
+        return True, None
+
+    with patch(
+        "instagram_scraper.workflows.video_downloads.download_video_file",
+    ) as mock_download:
+        mock_download.side_effect = mock_download_side_effect
+
+        summary = run(config)
+
+    assert summary["target_posts_considered"] == 2
+    assert summary["processed"] == 2
+    assert summary["downloaded_files"] == 2
+    assert mock_fetch.call_count == 1
+    assert mock_fetch.call_args.args[1] == "9999999999"
+    assert not (tmp_path / "videos" / "ABC123").exists()
+    assert (tmp_path / "videos" / "NEW456" / "NEW456_01.mp4").exists()
+
+
+@patch("instagram_scraper.workflows.video_downloads._build_session")
+@patch("instagram_scraper.workflows.video_downloads._fetch_media_info")
+def test_run_with_resume_ignores_invalid_checkpoint(
+    mock_fetch: MagicMock,
+    mock_build_session: MagicMock,
+    sample_posts_csv: Path,
+    mock_session: MagicMock,
+    tmp_path: Path,
+) -> None:
+    """Test resume mode falls back to a fresh run when checkpoint JSON is invalid."""
+    config = Config(
+        output_dir=tmp_path,
+        posts_csv=sample_posts_csv,
+        comments_csv=tmp_path / "comments.csv",
+        should_resume=True,
+        should_reset_output=False,
+        min_delay=0.01,
+        max_delay=0.02,
+        max_retries=3,
+        timeout=30,
+        checkpoint_every=10,
+        limit=None,
+        cookie_header="",
+        max_concurrent_downloads=2,
+    )
+    mock_build_session.return_value = mock_session
+    mock_fetch.return_value = (
+        {
+            "media_type": MEDIA_TYPE_VIDEO,
+            "video_versions": [
+                {"width": 1920, "height": 1080, "url": "https://example.com/video.mp4"},
+            ],
+        },
+        None,
+    )
+    (tmp_path / "videos_checkpoint.json").write_text("{not valid json")
+
+    def mock_download_side_effect(session, video_url, destination, cfg):
+        destination.parent.mkdir(parents=True, exist_ok=True)
+        destination.write_bytes(b"mock video content")
+        return True, None
+
+    with patch(
+        "instagram_scraper.workflows.video_downloads.download_video_file",
+    ) as mock_download:
+        mock_download.side_effect = mock_download_side_effect
+
+        summary = run(config)
+
+    assert summary["processed"] == 1
+    assert summary["downloaded_files"] == 1
+    assert mock_fetch.call_count == 1
+    saved_checkpoint = json.loads((tmp_path / "videos_checkpoint.json").read_text())
+    assert saved_checkpoint["completed"] is True
+
+
 # Test main
```

## Why these changes cover the request

This plan implements the prioritized action plan and the remaining medium-priority fixes:

- Quick wins
  - README auth guidance now prefers `.env` / `IG_COOKIE_HEADER`
  - `.gitignore` duplicate `.env` entry removed

- Medium-priority fixes
  - larger synthetic downloader fixture coverage
  - resume behavior coverage for modified inputs
  - corrupted-checkpoint resume fallback coverage

## Validation

```bash
uv run ruff check .
uv run ty check
c:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.venv/Scripts/python.exe -m pytest tests/test_download_instagram_videos.py
c:/Users/nicolas/Documents/GitHub/instagram/instagram-scraper/.venv/Scripts/python.exe -m pytest
```

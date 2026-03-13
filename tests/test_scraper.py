import importlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

import pandas as pd

scraper = importlib.import_module("instagram_scraper.scraper")


class LoaderRecord(TypedDict, total=False):
    download_targets: list[str]
    loader_kwargs: dict[str, object]


class FakePost:
    def __init__(
        self,
        *,
        shortcode: str,
        is_video: bool,
        video_url: str | None,
        url: str,
        comments: list[object] | None = None,
        likes: list[object] | None = None,
        comments_error: Exception | None = None,
        likes_error: Exception | None = None,
    ) -> None:
        self.shortcode = shortcode
        self.is_video = is_video
        self.video_url = video_url
        self.url = url
        self._comments = comments or []
        self._likes = likes or []
        self._comments_error = comments_error
        self._likes_error = likes_error

    def get_comments(self) -> list[object]:
        if self._comments_error is not None:
            raise self._comments_error
        return self._comments

    def get_likes(self) -> list[object]:
        if self._likes_error is not None:
            raise self._likes_error
        return self._likes


class FakeProfile:
    def __init__(self, posts: list[FakePost]) -> None:
        self._posts = posts

    def get_posts(self) -> list[FakePost]:
        return self._posts


class FakeLoader:
    def __init__(self, *, output_dir: Path, record: LoaderRecord, **kwargs) -> None:
        self.context = object()
        self.output_dir = output_dir
        self.record = record
        self.record["loader_kwargs"] = kwargs

    def download_post(self, post: FakePost, target: str) -> None:
        targets = self.record.setdefault("download_targets", [])
        targets.append(target)
        post_dir = self.output_dir / target
        post_dir.mkdir(parents=True, exist_ok=True)

        suffix = ".mp4" if post.is_video else ".jpg"
        (post_dir / f"{post.shortcode}{suffix}").write_text("media", encoding="utf-8")


def make_comment(username: str, text: str, likes: int = 0) -> object:
    return SimpleNamespace(
        owner=SimpleNamespace(username=username),
        text=text,
        created_at_utc=datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
        likes_count=likes,
    )


def make_liker(username: str) -> object:
    return SimpleNamespace(username=username)


def test_sanitize_folder_name_replaces_invalid_characters() -> None:
    assert scraper.sanitize_folder_name('bad<>:"/\\|?*name') == "bad_________name"


def test_sanitize_folder_name_trims_and_limits_length() -> None:
    assert scraper.sanitize_folder_name(f" {'a' * 60} ") == "a" * 50


def test_scrape_profile_downloads_media_and_exports_csvs(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    record: LoaderRecord = {}
    output_dir = tmp_path / "exports"
    posts = [
        FakePost(
            shortcode="POST1",
            is_video=False,
            video_url=None,
            url="https://instagram.com/p/POST1",
            comments=[make_comment("alice", "nice post", likes=3)],
            likes=[make_liker(f"user-{index}") for index in range(120)],
        ),
        FakePost(
            shortcode="REEL1",
            is_video=True,
            video_url="https://cdn.example/reel.mp4",
            url="https://instagram.com/reel/REEL1",
            comments=[make_comment("bob", "great reel")],
            likes=[make_liker("viewer")],
        ),
    ]

    monkeypatch.setattr(
        scraper.instaloader,
        "Instaloader",
        lambda **kwargs: FakeLoader(output_dir=output_dir, record=record, **kwargs),
    )
    monkeypatch.setattr(
        scraper.instaloader.Profile,
        "from_username",
        lambda context, username: FakeProfile(posts),
    )

    scraper.scrape_profile("natgeo", limit=2, output_dir=output_dir)

    assert record.get("download_targets") == ["post_POST1", "reel_REEL1"]
    assert record.get("loader_kwargs") == {
        "dirname_pattern": str(output_dir / "{target}"),
        "download_pictures": True,
        "download_videos": True,
        "download_video_thumbnails": False,
        "download_geotags": False,
        "download_comments": False,
        "save_metadata": False,
        "compress_json": False,
    }

    post_dir = output_dir / "post_POST1"
    reel_dir = output_dir / "reel_REEL1"

    assert (post_dir / "media.jpg").exists()
    assert (reel_dir / "media.mp4").exists()

    comments = pd.read_csv(post_dir / "comments.csv")
    assert comments.to_dict(orient="records") == [
        {
            "username": "alice",
            "comment_text": "nice post",
            "timestamp": "2024-01-02 03:04:05",
            "likes": 3,
        }
    ]

    likes = pd.read_csv(post_dir / "likes.csv")
    assert len(likes) == 100
    assert likes.iloc[0].to_dict() == {"username": "user-0"}
    assert likes.iloc[-1].to_dict() == {"username": "user-99"}

    output = capsys.readouterr().out
    assert "Fetching profile @natgeo" in output
    assert "Done! Scraped 2 posts/reels." in output


def test_scrape_profile_writes_empty_csvs_when_comments_or_likes_fail(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    record: LoaderRecord = {}
    output_dir = tmp_path / "exports"
    posts = [
        FakePost(
            shortcode="BROKEN1",
            is_video=False,
            video_url=None,
            url="https://instagram.com/p/BROKEN1",
            comments_error=RuntimeError("comments unavailable"),
            likes_error=RuntimeError("likes unavailable"),
        ),
        FakePost(
            shortcode="SKIPME",
            is_video=False,
            video_url=None,
            url="https://instagram.com/p/SKIPME",
        ),
    ]

    monkeypatch.setattr(
        scraper.instaloader,
        "Instaloader",
        lambda **kwargs: FakeLoader(output_dir=output_dir, record=record, **kwargs),
    )
    monkeypatch.setattr(
        scraper.instaloader.Profile,
        "from_username",
        lambda context, username: FakeProfile(posts),
    )

    scraper.scrape_profile("natgeo", limit=1, output_dir=output_dir)

    assert record.get("download_targets") == ["post_BROKEN1"]
    assert not (output_dir / "post_SKIPME").exists()

    comments = pd.read_csv(output_dir / "post_BROKEN1" / "comments.csv")
    likes = pd.read_csv(output_dir / "post_BROKEN1" / "likes.csv")

    assert list(comments.columns) == ["username", "comment_text", "timestamp", "likes"]
    assert comments.empty
    assert list(likes.columns) == ["username"]
    assert likes.empty

    output = capsys.readouterr().out
    assert "Warning: Could not fetch all comments: comments unavailable" in output
    assert (
        "Warning: Could not fetch likes (common limitation): likes unavailable"
        in output
    )

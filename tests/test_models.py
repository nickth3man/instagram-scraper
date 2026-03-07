from instagram_scraper.models import (
    ErrorRecord,
    PostRecord,
    RawCaptureRecord,
    StoryRecord,
    UserRecord,
)


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

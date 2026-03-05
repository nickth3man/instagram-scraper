from instagram_scraper.models import PostRecord


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

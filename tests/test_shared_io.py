import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

shared_io = importlib.import_module("instagram_scraper._shared_io")


def test_write_json_line_serializes_path_values(tmp_path: Path) -> None:
    path = tmp_path / "records.ndjson"
    shared_io.write_json_line(path, {"output_dir": Path("data/example")})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["output_dir"] == str(Path("data") / "example")


def test_write_json_line_serializes_datetime_values(tmp_path: Path) -> None:
    path = tmp_path / "records.ndjson"
    timestamp = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)
    shared_io.write_json_line(path, {"taken_at_utc": timestamp})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["taken_at_utc"] == "2026-03-05T12:00:00+00:00"

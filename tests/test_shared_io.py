import importlib
from pathlib import Path

shared_io = importlib.import_module("instagram_scraper._shared_io")


def test_write_json_line_serializes_path_values(tmp_path: Path) -> None:
    path = tmp_path / "records.ndjson"
    shared_io.write_json_line(path, {"output_dir": Path("data/example")})
    assert '"output_dir": "data\\\\example"' in path.read_text(encoding="utf-8")

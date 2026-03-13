from __future__ import annotations

import pytest

from instagram_scraper.workflows import generate_extraction_commands


def test_main_writes_manual_instructions(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "tool_dump.json"
    input_path.write_text(
        '{"urls": ["https://www.instagram.com/p/abc123/", "https://www.instagram.com/reel/xyz789/"]}',
        encoding="utf-8",
    )

    exit_code = generate_extraction_commands.main(
        ["--input", str(input_path), "--limit", "1"],
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Generated extraction commands" in captured.out
    assert "# Extracting: abc123" in captured.out
    assert "Navigate to: https://www.instagram.com/p/abc123/" in captured.out
    assert "xyz789" not in captured.out


def test_main_rejects_non_list_urls(tmp_path) -> None:
    input_path = tmp_path / "tool_dump.json"
    input_path.write_text('{"urls": "not-a-list"}', encoding="utf-8")

    with pytest.raises(TypeError, match="Expected 'urls' to be a list"):
        generate_extraction_commands.main(["--input", str(input_path)])

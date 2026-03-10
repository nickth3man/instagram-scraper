from pathlib import Path


MAX_PYTHON_FILE_LINES = 550
PROJECT_DIRECTORIES = ("src", "tests", "scripts")
SKIP_DIRECTORY_NAMES = {"__pycache__", ".venv", ".git"}


def _iter_project_python_files(project_root: Path) -> list[Path]:
    python_files: list[Path] = []
    for directory_name in PROJECT_DIRECTORIES:
        directory = project_root / directory_name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.py")):
            if any(part in SKIP_DIRECTORY_NAMES for part in path.parts):
                continue
            python_files.append(path)
    return python_files


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as file_handle:
        return sum(1 for _ in file_handle)


def test_python_files_stay_within_ai_friendly_size_limit() -> None:
    """Keep Python files small enough for reliable AI-assisted editing."""
    project_root = Path(__file__).resolve().parent.parent
    violations: list[str] = []

    for path in _iter_project_python_files(project_root):
        line_count = _count_lines(path)
        relative_path = path.relative_to(project_root).as_posix()
        if line_count > MAX_PYTHON_FILE_LINES:
            violations.append(
                f"{relative_path}: {line_count} lines (exceeds {MAX_PYTHON_FILE_LINES})"
            )

    assert not violations, "Files exceeding AI-friendly size limit:\n" + "\n".join(violations)

# Copyright (c) 2026
"""Project-local environment loading helpers."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env(env_path: Path = ENV_FILE) -> None:
    """Populate missing environment variables from the local `.env` file.

    Parameters
    ----------
    env_path : Path
        The env file to read.
    """
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        normalized_key = key.strip()
        if not normalized_key or normalized_key in os.environ:
            continue
        normalized_value = raw_value.strip().strip('"').strip("'")
        os.environ[normalized_key] = normalized_value

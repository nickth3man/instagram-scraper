# Copyright (c) 2026
"""Shared fail-fast Instaloader helpers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, override

from instaloader import Instaloader
from instaloader.exceptions import BadResponseException, TooManyRequestsException
from instaloader.instaloadercontext import RateController

from instagram_scraper.infrastructure.env import load_project_env

if TYPE_CHECKING:
    from pathlib import Path

FAIL_FAST_429_TEMPLATE = "fail-fast-429:{}"
DEFAULT_INSTALOADER_TIMEOUT_SECONDS = 20.0


class FailFastBadResponseRateController(RateController):
    """Raise a bad-response error immediately when Instagram returns HTTP 429."""

    @override
    def handle_429(self, query_type: str) -> None:
        raise BadResponseException(FAIL_FAST_429_TEMPLATE.format(query_type))


class FailFastTooManyRequestsRateController(RateController):
    """Raise a too-many-requests error immediately when Instagram returns HTTP 429."""

    @override
    def handle_429(self, query_type: str) -> None:
        raise TooManyRequestsException(FAIL_FAST_429_TEMPLATE.format(query_type))


def load_cookie_header(*, env_var: str = "IG_COOKIE_HEADER") -> str:
    """Load an Instagram cookie header from the project environment.

    Returns
    -------
        Raw cookie header string, or an empty string when unset.
    """
    load_project_env()
    return os.getenv(env_var, "").strip()


def cookie_dict(cookie_header: str) -> dict[str, str]:
    """Parse a cookie header into an Instaloader-ready cookie dictionary.

    Returns
    -------
        Mapping of cookie names to values.
    """
    return {
        key.strip(): value.strip()
        for part in cookie_header.split(";")
        if "=" in part
        for key, value in [part.split("=", 1)]
    }


def build_failfast_instaloader(
    *,
    dirname_pattern: str,
    download_media: bool,
    request_timeout: float = DEFAULT_INSTALOADER_TIMEOUT_SECONDS,
    rate_controller: type[RateController] = FailFastTooManyRequestsRateController,
) -> Instaloader:
    """Return an Instaloader configured to fail immediately on rate limiting.

    Returns
    -------
        Configured Instaloader instance with retry sleeping disabled.
    """
    return Instaloader(
        dirname_pattern=dirname_pattern,
        filename_pattern="{shortcode}",
        download_pictures=download_media,
        download_videos=download_media,
        download_video_thumbnails=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        sleep=False,
        max_connection_attempts=1,
        request_timeout=request_timeout,
        rate_controller=rate_controller,
    )


def checkpoint_path(output_dir: Path) -> Path:
    """Return the checkpoint file path used by the fail-fast URL workflow.

    Returns
    -------
        Path to the workflow checkpoint JSON file.
    """
    return output_dir / "checkpoint_instaloader.json"

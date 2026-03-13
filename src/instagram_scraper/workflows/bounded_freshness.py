# Copyright (c) 2026
"""Bounded freshness verification for the believerofbuckets closure task."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

from instaloader import Post
from instaloader.exceptions import BadResponseException, InstaloaderException
from requests import RequestException

from instagram_scraper.infrastructure.env import load_project_env
from instagram_scraper.infrastructure.files import atomic_write_text
from instagram_scraper.infrastructure.instagram_http import (
    build_instagram_client,
    get_json_payload,
)
from instagram_scraper.workflows._instaloader_failfast import (
    FailFastBadResponseRateController,
    build_failfast_instaloader,
    cookie_dict,
)

if TYPE_CHECKING:
    from requests import Response


DEFAULT_SHORTCODE = "DVsHusCjCTU"
DEFAULT_EVIDENCE_DIR = Path(".sisyphus/evidence")
DEFAULT_INSTALOADER_TIMEOUT_SECONDS = 20.0
DEFAULT_FALLBACK_TIMEOUT_SECONDS = 20.0
SUCCESS_EXIT_CODE = 0
SUCCESS_STATUS = 200
UNEXPECTED_SUCCESS_EXIT_CODE = 1
INSTALOADER_FILENAME_PATTERN = "{shortcode}"

CheckOutcome = Literal["blocked", "unexpected_success"]


class _VerificationCheck(Protocol):
    def __call__(
        self,
        shortcode: str,
        cookie_header: str,
        timeout_seconds: float,
    ) -> _CheckResult: ...


@dataclass(frozen=True, slots=True)
class _CheckResult:
    name: str
    outcome: CheckOutcome
    detail: str
    status_code: int | None
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of writing one bounded freshness evidence bundle.

    Returns
    -------
        A stable record of the written evidence path, payload, and exit code.
    """

    evidence_path: Path
    payload: dict[str, object]
    exit_code: int


@dataclass(frozen=True, slots=True)
class _VerificationSettings:
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR
    cookie_header: str | None = None
    instaloader_timeout_seconds: float = DEFAULT_INSTALOADER_TIMEOUT_SECONDS
    fallback_timeout_seconds: float = DEFAULT_FALLBACK_TIMEOUT_SECONDS
    checks: tuple[_VerificationCheck, _VerificationCheck] | None = None
    now: datetime | None = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the bounded freshness verifier.

    Returns
    -------
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortcode", default=DEFAULT_SHORTCODE)
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--cookie-header")
    parser.add_argument(
        "--instaloader-timeout-seconds",
        type=float,
        default=DEFAULT_INSTALOADER_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--fallback-timeout-seconds",
        type=float,
        default=DEFAULT_FALLBACK_TIMEOUT_SECONDS,
    )
    return parser.parse_args()


def verify_shortcode_freshness(
    shortcode: str = DEFAULT_SHORTCODE,
    *,
    settings: _VerificationSettings | None = None,
) -> VerificationResult:
    """Run bounded freshness checks and persist a timestamped evidence bundle.

    Returns
    -------
        Verification result including the written evidence path and exit code.

    """
    resolved_settings = settings or _VerificationSettings()
    resolved_cookie_header = resolved_settings.cookie_header or _load_cookie_header()
    _validate_timeout(
        resolved_settings.instaloader_timeout_seconds,
        label="instaloader",
    )
    _validate_timeout(
        resolved_settings.fallback_timeout_seconds,
        label="fallback",
    )
    generated_at = resolved_settings.now or datetime.now(tz=UTC)
    selected_checks = resolved_settings.checks or (
        _run_instaloader_shortcode_check,
        _run_shortcode_api_check,
    )
    check_results = [
        selected_checks[0](
            shortcode,
            resolved_cookie_header,
            resolved_settings.instaloader_timeout_seconds,
        ),
        selected_checks[1](
            shortcode,
            resolved_cookie_header,
            resolved_settings.fallback_timeout_seconds,
        ),
    ]
    has_unexpected_success = any(
        result.outcome == "unexpected_success" for result in check_results
    )
    payload = _build_payload(
        shortcode=shortcode,
        generated_at=generated_at,
        check_results=check_results,
        instaloader_timeout_seconds=resolved_settings.instaloader_timeout_seconds,
        fallback_timeout_seconds=resolved_settings.fallback_timeout_seconds,
    )
    evidence_path = _evidence_path(
        resolved_settings.evidence_dir,
        shortcode,
        generated_at,
    )
    resolved_settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(evidence_path, json.dumps(payload, indent=2, sort_keys=True))
    return VerificationResult(
        evidence_path=evidence_path,
        payload=payload,
        exit_code=(UNEXPECTED_SUCCESS_EXIT_CODE if has_unexpected_success else 0),
    )


def main() -> int:
    """Run the bounded verifier CLI and emit the written evidence metadata.

    Returns
    -------
        Process exit code for the freshness check.
    """
    args = parse_args()
    result = verify_shortcode_freshness(
        shortcode=args.shortcode,
        settings=_VerificationSettings(
            evidence_dir=Path(args.evidence_dir),
            cookie_header=args.cookie_header,
            instaloader_timeout_seconds=args.instaloader_timeout_seconds,
            fallback_timeout_seconds=args.fallback_timeout_seconds,
        ),
    )
    sys.stdout.write(
        json.dumps(
            {
                "shortcode": args.shortcode,
                "evidence_path": str(result.evidence_path),
                "overall_outcome": result.payload["overall_outcome"],
                "exit_code": result.exit_code,
            },
        )
        + "\n",
    )
    return result.exit_code


def _load_cookie_header() -> str:
    load_project_env()
    cookie_header = os.getenv("IG_COOKIE_HEADER", "").strip()
    if cookie_header:
        return cookie_header
    message = "IG_COOKIE_HEADER is required for bounded freshness verification"
    raise ValueError(message)


def _validate_timeout(timeout_seconds: float, *, label: str) -> None:
    if timeout_seconds <= 0:
        message = f"{label} timeout must be positive"
        raise ValueError(message)


def _run_instaloader_shortcode_check(
    shortcode: str,
    cookie_header: str,
    timeout_seconds: float,
) -> _CheckResult:
    started = time.monotonic()
    cookies = cookie_dict(cookie_header)
    username = cookies.get("ds_user_id", "session")
    loader = build_failfast_instaloader(
        dirname_pattern="{target}",
        download_media=False,
        request_timeout=timeout_seconds,
        rate_controller=FailFastBadResponseRateController,
    )
    try:
        loader.load_session(username, cookies)
        post = Post.from_shortcode(loader.context, shortcode)
    except (BadResponseException, InstaloaderException, KeyError, ValueError) as exc:
        return _CheckResult(
            name="instaloader_fail_fast",
            outcome="blocked",
            detail=type(exc).__name__,
            status_code=None,
            duration_seconds=round(time.monotonic() - started, 3),
        )
    return _CheckResult(
        name="instaloader_fail_fast",
        outcome="unexpected_success",
        detail=_unexpected_success_detail(post.shortcode, extra=post.typename),
        status_code=SUCCESS_STATUS,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def _run_shortcode_api_check(
    shortcode: str,
    cookie_header: str,
    timeout_seconds: float,
) -> _CheckResult:
    started = time.monotonic()
    session = build_instagram_client(cookie_header, max_retries=0)
    url = f"https://www.instagram.com/api/v1/media/shortcode/{shortcode}/info/"
    try:
        response = session.get(url, timeout=timeout_seconds)
    except RequestException as exc:
        session.close()
        return _CheckResult(
            name="shortcode_api",
            outcome="blocked",
            detail=type(exc).__name__,
            status_code=None,
            duration_seconds=round(time.monotonic() - started, 3),
        )
    result = _shortcode_api_response_result(
        shortcode=shortcode,
        response=response,
        started=started,
    )
    session.close()
    return result


def _shortcode_api_response_result(
    *,
    shortcode: str,
    response: Response,
    started: float,
) -> _CheckResult:
    payload = get_json_payload(response)
    items = payload.get("items") if payload is not None else None
    if response.status_code == SUCCESS_STATUS and isinstance(items, list) and items:
        first = items[0]
        if isinstance(first, dict):
            first_dict = cast("dict[str, object]", first)
            shortcode_value = first_dict.get("code")
            resolved_shortcode = (
                shortcode_value if isinstance(shortcode_value, str) else shortcode
            )
            return _CheckResult(
                name="shortcode_api",
                outcome="unexpected_success",
                detail=_unexpected_success_detail(
                    shortcode,
                    extra=resolved_shortcode,
                ),
                status_code=response.status_code,
                duration_seconds=round(time.monotonic() - started, 3),
            )
    detail = f"http_{response.status_code}"
    return _CheckResult(
        name="shortcode_api",
        outcome="blocked",
        detail=detail,
        status_code=response.status_code,
        duration_seconds=round(time.monotonic() - started, 3),
    )


def _unexpected_success_detail(shortcode: str, *, extra: str) -> str:
    return f"shortcode_resolved:{shortcode}:{extra}"


def _build_payload(
    *,
    shortcode: str,
    generated_at: datetime,
    check_results: list[_CheckResult],
    instaloader_timeout_seconds: float,
    fallback_timeout_seconds: float,
) -> dict[str, object]:
    overall_outcome = (
        "unexpected_success"
        if any(result.outcome == "unexpected_success" for result in check_results)
        else "blocked"
    )
    return {
        "shortcode": shortcode,
        "generated_at": generated_at.isoformat(),
        "overall_outcome": overall_outcome,
        "selected_checks": [result.name for result in check_results],
        "timeouts_seconds": {
            "instaloader_fail_fast": instaloader_timeout_seconds,
            "shortcode_api": fallback_timeout_seconds,
        },
        "checks": [asdict(result) for result in check_results],
    }


def _evidence_path(evidence_dir: Path, shortcode: str, generated_at: datetime) -> Path:
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    return evidence_dir / f"bounded-freshness-{shortcode}-{timestamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())

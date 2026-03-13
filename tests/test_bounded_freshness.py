from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from instagram_scraper.workflows.bounded_freshness import (
    UNEXPECTED_SUCCESS_EXIT_CODE,
    _CheckResult,
    _VerificationSettings,
    verify_shortcode_freshness,
)


def _blocked_check(name: str):
    def _run(
        shortcode: str,
        cookie_header: str,
        timeout_seconds: float,
    ) -> _CheckResult:
        del shortcode, cookie_header, timeout_seconds
        return _CheckResult(
            name=name,
            outcome="blocked",
            detail="http_429",
            status_code=429,
            duration_seconds=0.25,
        )

    return _run


def _unexpected_success_check(
    shortcode: str,
    cookie_header: str,
    timeout_seconds: float,
) -> _CheckResult:
    del cookie_header, timeout_seconds
    return _CheckResult(
        name="shortcode_api",
        outcome="unexpected_success",
        detail=f"shortcode_resolved:{shortcode}:GraphVideo",
        status_code=200,
        duration_seconds=0.1,
    )


def test_verify_shortcode_freshness_writes_blocked_evidence_bundle(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 3, 10, 12, 30, 45, tzinfo=UTC)

    result = verify_shortcode_freshness(
        settings=_VerificationSettings(
            evidence_dir=tmp_path,
            cookie_header="sessionid=test; ds_user_id=123",
            checks=(
                _blocked_check("instaloader_fail_fast"),
                _blocked_check("shortcode_api"),
            ),
            now=now,
        ),
    )

    assert result.exit_code == 0
    assert result.evidence_path == (
        tmp_path / "bounded-freshness-DVsHusCjCTU-20260310T123045Z.json"
    )
    assert result.payload["overall_outcome"] == "blocked"
    assert result.payload["selected_checks"] == [
        "instaloader_fail_fast",
        "shortcode_api",
    ]
    evidence_payload = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    payload = cast("dict[str, object]", evidence_payload)
    checks = cast("list[dict[str, object]]", payload["checks"])
    assert payload["shortcode"] == "DVsHusCjCTU"
    assert checks[0]["detail"] == "http_429"
    assert checks[1]["status_code"] == 429


def test_verify_shortcode_freshness_fails_closed_on_unexpected_success(
    tmp_path: Path,
) -> None:
    result = verify_shortcode_freshness(
        settings=_VerificationSettings(
            evidence_dir=tmp_path,
            cookie_header="sessionid=test; ds_user_id=123",
            checks=(
                _blocked_check("instaloader_fail_fast"),
                _unexpected_success_check,
            ),
            now=datetime(2026, 3, 10, 12, 31, 0, tzinfo=UTC),
        ),
    )

    assert result.exit_code == UNEXPECTED_SUCCESS_EXIT_CODE
    assert result.payload["overall_outcome"] == "unexpected_success"
    checks = cast("list[dict[str, object]]", result.payload["checks"])
    assert checks[1]["outcome"] == "unexpected_success"
    assert checks[1]["detail"] == (
        "shortcode_resolved:DVsHusCjCTU:GraphVideo"
    )

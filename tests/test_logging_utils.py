import structlog

from instagram_scraper.infrastructure.structured_logging import (
    build_logger,
    configure_logging,
)


def test_build_logger_binds_run_context() -> None:
    configure_logging()
    logger = build_logger(run_id="run-1", mode="profile")
    with structlog.testing.capture_logs() as captured:
        logger.bind(stage="preflight").info("starting")
    assert captured == [
        {
            "event": "starting",
            "mode": "profile",
            "run_id": "run-1",
            "stage": "preflight",
            "log_level": "info",
        },
    ]

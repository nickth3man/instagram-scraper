from instagram_scraper.logging_utils import build_logger


def test_build_logger_binds_run_context() -> None:
    logger = build_logger(run_id="run-1", mode="profile")
    logger.bind(stage="preflight").info("starting")
    assert logger is not None

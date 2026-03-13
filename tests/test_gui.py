"""Tests for the Instagram Scraper GUI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from instagram_scraper.core.capabilities import AUTH_REQUIRED_MODES
from instagram_scraper.core.pipeline import PipelineCancelledError
from instagram_scraper.ui.gui import (
    EVENT_EXIT,
    EVENT_PROGRESS_UPDATE,
    EVENT_SCRAPE_ERROR,
    EVENT_START_SCRAPE,
    EVENT_STOP_SCRAPE,
    ScraperWorker,
    _handle_progress_update,
    _handle_scrape_complete,
    _handle_scrape_error,
    _process_event,
    _validate_auth_for_mode,
    build_scrape_kwargs,
    get_shared_settings,
)

WORKER_TIMEOUT_SECONDS = 1.0


def _wait_for_worker(worker: ScraperWorker) -> None:
    assert worker.wait_for_completion(WORKER_TIMEOUT_SECONDS)


class TestScraperWorker:
    """Tests for the ScraperWorker class."""

    def test_worker_initialization(self) -> None:
        """Test that ScraperWorker initializes correctly."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        assert worker.window == mock_window
        assert worker._thread is None
        assert not worker._stop_event.is_set()

    def test_worker_is_running_not_started(self) -> None:
        """Test is_running returns False when not started."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        assert not worker.is_running()

    def test_worker_start_and_stop(self) -> None:
        """Test that worker can be started and stopped."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        # Mock execute_pipeline to avoid actual execution
        with patch("instagram_scraper.ui.gui.execute_pipeline") as mock_execute:
            mock_execute.return_value = MagicMock(model_dump=lambda: {"posts": 1})

            worker.start_scrape("profile", {"username": "test"})

            assert worker.is_running() or worker._thread is not None
            _wait_for_worker(worker)

            worker.request_stop()
            assert worker._stop_event.is_set()

    def test_worker_stop_event_passed_to_pipeline(self) -> None:
        """Test that stop event is passed to execute_pipeline."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        with patch("instagram_scraper.ui.gui.execute_pipeline") as mock_execute:
            mock_execute.return_value = MagicMock(model_dump=lambda: {"posts": 1})

            worker.start_scrape("profile", {"username": "test"})
            _wait_for_worker(worker)

            # Check that execute_pipeline was called with cancellation_event
            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args[1]
            assert "cancellation_event" in call_kwargs
            assert call_kwargs["cancellation_event"] == worker._stop_event


class TestBuildScrapeKwargs:
    """Tests for build_scrape_kwargs function."""

    def test_profile_mode_requires_username(self) -> None:
        """Test that profile mode requires username."""
        values = {
            "-OUTPUT-DIR-": "data",
            "-COOKIE-HEADER-": "",
            "-LIMIT-": "",
            "-REQUEST-TIMEOUT-": "30",
            "-MAX-RETRIES-": "5",
            "-PROFILE-USERNAME-": "",
        }

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error") as mock_popup:
            result = build_scrape_kwargs("profile", values)
            assert result is None
            mock_popup.assert_called_once()

    def test_profile_mode_valid_input(self) -> None:
        """Test profile mode with valid input."""
        values = {
            "-OUTPUT-DIR-": "data",
            "-COOKIE-HEADER-": "sessionid=abc",
            "-LIMIT-": "100",
            "-REQUEST-TIMEOUT-": "30",
            "-MAX-RETRIES-": "5",
            "-CHECKPOINT-EVERY-": "20",
            "-RAW-CAPTURES-": True,
            "-MIN-DELAY-": "0.05",
            "-MAX-DELAY-": "0.2",
            "-PROFILE-USERNAME-": "testuser",
        }

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error"):
            result = build_scrape_kwargs("profile", values)

        assert result is not None
        assert result["username"] == "testuser"
        assert result["output_dir"] == Path("data")
        assert result["has_auth"] is True
        assert result["limit"] == 100
        assert result["checkpoint_every"] == 20
        assert result["raw_captures"] is True
        assert result["min_delay"] == 0.05
        assert result["max_delay"] == 0.2

    def test_hashtag_mode_requires_hashtag(self) -> None:
        """Test that hashtag mode requires hashtag input."""
        values = {
            "-OUTPUT-DIR-": "data",
            "-COOKIE-HEADER-": "",
            "-HASHTAG-HASHTAG-": "",
        }

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error") as mock_popup:
            result = build_scrape_kwargs("hashtag", values)
            assert result is None
            mock_popup.assert_called_once()


class TestAuthValidation:
    """Tests for authentication validation."""

    def test_auth_required_modes(self) -> None:
        """Test that auth-required modes are correctly identified."""
        expected_auth_modes = {
            "hashtag",
            "location",
            "stories",
            "followers",
            "following",
            "likers",
            "sync:hashtag",
            "sync:location",
            "commenters",
        }
        assert expected_auth_modes == AUTH_REQUIRED_MODES

    def test_validate_auth_for_mode_with_cookie(self) -> None:
        """Test validation passes when cookie is provided."""
        values = {"-COOKIE-HEADER-": "sessionid=abc123"}

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error") as mock_popup:
            result = _validate_auth_for_mode("hashtag", values)
            assert result is True
            mock_popup.assert_not_called()

    def test_validate_auth_for_mode_without_cookie(self) -> None:
        """Test validation fails when cookie is missing for auth-required mode."""
        values = {"-COOKIE-HEADER-": ""}

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error") as mock_popup:
            result = _validate_auth_for_mode("hashtag", values)
            assert result is False
            mock_popup.assert_called_once()
            assert "requires authentication" in str(mock_popup.call_args)

    def test_validate_auth_for_mode_not_required(self) -> None:
        """Test validation passes for non-auth modes without cookie."""
        values = {"-COOKIE-HEADER-": ""}

        with patch("instagram_scraper.ui.gui.FreeSimpleGUI.popup_error") as mock_popup:
            result = _validate_auth_for_mode("profile", values)
            assert result is True
            mock_popup.assert_not_called()


class TestSharedSettings:
    """Tests for get_shared_settings function."""

    def test_default_settings(self) -> None:
        """Test default settings extraction."""
        values = {
            "-OUTPUT-DIR-": "data",
            "-COOKIE-HEADER-": "",
            "-LIMIT-": "",
            "-REQUEST-TIMEOUT-": "30",
            "-MAX-RETRIES-": "5",
            "-CHECKPOINT-EVERY-": "20",
            "-RAW-CAPTURES-": False,
            "-MIN-DELAY-": "0.05",
            "-MAX-DELAY-": "0.2",
        }

        settings = get_shared_settings(values)

        assert settings["output_dir"] == Path("data")
        assert settings["has_auth"] is False
        assert "limit" not in settings
        assert settings["request_timeout"] == 30
        assert settings["max_retries"] == 5
        assert settings["checkpoint_every"] == 20
        assert settings["raw_captures"] is False
        assert settings["min_delay"] == 0.05
        assert settings["max_delay"] == 0.2

    def test_custom_settings(self) -> None:
        """Test custom settings extraction."""
        values = {
            "-OUTPUT-DIR-": "/custom/path",
            "-COOKIE-HEADER-": "sessionid=test",
            "-LIMIT-": "500",
            "-REQUEST-TIMEOUT-": "60",
            "-MAX-RETRIES-": "10",
            "-CHECKPOINT-EVERY-": "50",
            "-RAW-CAPTURES-": True,
            "-MIN-DELAY-": "0.1",
            "-MAX-DELAY-": "0.5",
        }

        settings = get_shared_settings(values)

        assert settings["output_dir"] == Path("/custom/path")
        assert settings["has_auth"] is True
        assert settings["limit"] == 500
        assert settings["request_timeout"] == 60
        assert settings["max_retries"] == 10
        assert settings["checkpoint_every"] == 50
        assert settings["raw_captures"] is True
        assert settings["min_delay"] == 0.1
        assert settings["max_delay"] == 0.5


class TestEventHandlers:
    """Tests for event handling functions."""

    def test_handle_scrape_complete_success(self) -> None:
        """Test handling successful scrape completion."""
        mock_window = MagicMock()
        result = {
            "success": True,
            "summary": {
                "users": 5,
                "posts": 100,
                "comments": 500,
                "stories": 0,
                "errors": 0,
                "output_dir": "/data/test",
            },
        }

        _handle_scrape_complete(mock_window, result)

        mock_window.__getitem__.return_value.update.assert_any_call(
            "Scrape completed successfully!\n",
            append=True,
        )
        mock_window.__getitem__.assert_any_call("-STATUS-TEXT-")

    def test_handle_scrape_error_with_type(self) -> None:
        """Test handling scrape error with error type."""
        mock_window = MagicMock()
        result = {
            "error": "Rate limit exceeded",
            "detail": "Traceback...",
            "error_type": "rate_limit",
            "retry_after": 60,
        }

        _handle_scrape_error(mock_window, result)

        mock_window.__getitem__.return_value.update.assert_any_call(
            "Retry after: 60 seconds\n",
            append=True,
        )
        mock_window.__getitem__.assert_any_call("-STATUS-TEXT-")

    def test_handle_scrape_error_cancelled(self) -> None:
        """Test handling cancelled scrape."""
        mock_window = MagicMock()
        result = {"error": "Cancelled", "cancelled": True}

        _handle_scrape_error(mock_window, result)

        mock_window.__getitem__.return_value.update.assert_any_call(
            "Scrape cancelled by user.\n",
            append=True,
        )

    def test_handle_progress_update_valid(self) -> None:
        """Test handling valid progress update."""
        mock_window = MagicMock()
        values = {EVENT_PROGRESS_UPDATE: (50, 100)}

        _handle_progress_update(mock_window, values)

        mock_window.__getitem__.assert_called_with("-PROGRESS-BAR-")

    def test_handle_progress_update_invalid(self) -> None:
        """Test handling invalid progress update."""
        mock_window = MagicMock()
        values = {EVENT_PROGRESS_UPDATE: "invalid"}

        _handle_progress_update(mock_window, values)

        mock_window.__getitem__.assert_not_called()


class TestProcessEvent:
    """Tests for _process_event function."""

    def test_exit_event(self) -> None:
        """Test that exit event stops the loop."""
        mock_window = MagicMock()
        mock_worker = MagicMock()

        result = _process_event(mock_window, mock_worker, EVENT_EXIT, {})

        assert result is False

    def test_clear_log_event(self) -> None:
        """Test that clear log event clears the log output."""
        mock_window = MagicMock()
        mock_worker = MagicMock()

        result = _process_event(mock_window, mock_worker, "-CLEAR-LOG-", {})

        assert result is True
        mock_window.__getitem__.assert_called_with("-LOG-OUTPUT-")

    def test_stop_scrape_event(self) -> None:
        """Test that stop scrape event requests stop."""
        mock_window = MagicMock()
        mock_worker = MagicMock()

        result = _process_event(mock_window, mock_worker, EVENT_STOP_SCRAPE, {})

        assert result is True
        mock_worker.request_stop.assert_called_once()

    def test_progress_update_event(self) -> None:
        """Test that progress update event is handled."""
        mock_window = MagicMock()
        mock_worker = MagicMock()
        values = {EVENT_PROGRESS_UPDATE: (75, 100)}

        result = _process_event(mock_window, mock_worker, EVENT_PROGRESS_UPDATE, values)

        assert result is True

    def test_start_scrape_event(self) -> None:
        """Test that start scrape event initiates scraping."""
        mock_window = MagicMock()
        mock_worker = MagicMock()

        values = {
            "-OUTPUT-DIR-": "data",
            "-COOKIE-HEADER-": "",
            "-LIMIT-": "",
            "-REQUEST-TIMEOUT-": "30",
            "-MAX-RETRIES-": "5",
            "-PROFILE-USERNAME-": "testuser",
        }

        with patch(
            "instagram_scraper.ui.gui._validate_auth_for_mode",
            return_value=True,
        ):
            result = _process_event(
                mock_window,
                mock_worker,
                f"{EVENT_START_SCRAPE}profile",
                values,
            )

        assert result is True


class TestErrorTypes:
    """Tests for typed error handling."""

    def test_scraper_worker_handles_rate_limit_error(self) -> None:
        """Test that ScraperWorker handles RateLimitError correctly."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        from instagram_scraper.exceptions import RateLimitError

        with patch("instagram_scraper.ui.gui.execute_pipeline") as mock_execute:
            mock_execute.side_effect = RateLimitError(
                "Rate limited",
                retry_after=60,
            )

            worker.start_scrape("profile", {"username": "test"})
            _wait_for_worker(worker)

            mock_window.write_event_value.assert_called()
            call_args = mock_window.write_event_value.call_args[0]
            assert call_args[0] == EVENT_SCRAPE_ERROR
            assert call_args[1]["error_type"] == "rate_limit"
            assert call_args[1]["retry_after"] == 60

    def test_scraper_worker_handles_authentication_error(self) -> None:
        """Test that ScraperWorker handles AuthenticationError correctly."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        from instagram_scraper.exceptions import AuthenticationError

        with patch("instagram_scraper.ui.gui.execute_pipeline") as mock_execute:
            mock_execute.side_effect = AuthenticationError("Invalid cookie")

            worker.start_scrape("profile", {"username": "test"})
            _wait_for_worker(worker)

            mock_window.write_event_value.assert_called()
            call_args = mock_window.write_event_value.call_args[0]
            assert call_args[0] == EVENT_SCRAPE_ERROR
            assert call_args[1]["error_type"] == "authentication"

    def test_scraper_worker_handles_cancellation(self) -> None:
        """Test that ScraperWorker handles PipelineCancelledError correctly."""
        mock_window = MagicMock()
        worker = ScraperWorker(mock_window)

        with patch("instagram_scraper.ui.gui.execute_pipeline") as mock_execute:
            mock_execute.side_effect = PipelineCancelledError()

            worker.start_scrape("profile", {"username": "test"})
            _wait_for_worker(worker)

            mock_window.write_event_value.assert_called()
            call_args = mock_window.write_event_value.call_args[0]
            assert call_args[0] == EVENT_SCRAPE_ERROR
            assert call_args[1].get("cancelled") is True

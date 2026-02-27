"""Unit tests for the main.py CLI entry point."""

import json
import logging
import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_agent():
    return MagicMock()


@pytest.fixture
def patched_run(mock_agent):
    """Patch create_agent so run() never hits AWS."""
    with patch("main.create_agent", return_value=mock_agent):
        yield mock_agent


@pytest.mark.unit
class TestRunValidInput:
    def test_valid_date_invokes_agent(self, patched_run):
        with patch("builtins.input", return_value="1990-05-15"):
            import main
            main.run()
        patched_run.assert_called_once()

    def test_valid_date_passes_birthdate_in_prompt(self, patched_run):
        with patch("builtins.input", return_value="2000-01-01"):
            import main
            main.run()
        call_args = patched_run.call_args[0][0]
        assert "2000-01-01" in call_args

    def test_valid_date_does_not_exit(self, patched_run):
        with patch("builtins.input", return_value="1985-12-31"):
            import main
            # Should not raise SystemExit
            main.run()

    def test_strips_whitespace_from_input(self, patched_run):
        with patch("builtins.input", return_value="  1990-05-15  "):
            import main
            main.run()
        patched_run.assert_called_once()


@pytest.mark.unit
class TestRunInvalidInput:
    def test_non_date_string_exits_with_code_1(self, patched_run):
        with patch("builtins.input", return_value="not-a-date"):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1

    def test_partial_date_exits_with_code_1(self, patched_run):
        with patch("builtins.input", return_value="1990-05"):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1

    def test_empty_string_exits_with_code_1(self, patched_run):
        with patch("builtins.input", return_value=""):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1

    def test_invalid_date_prints_error_with_bad_input(self, patched_run, capsys):
        bad = "garbage-input"
        with patch("builtins.input", return_value=bad):
            with pytest.raises(SystemExit):
                import main
                main.run()
        captured = capsys.readouterr()
        assert bad in captured.out

    def test_invalid_date_does_not_invoke_agent(self, patched_run):
        with patch("builtins.input", return_value="not-a-date"):
            with pytest.raises(SystemExit):
                import main
                main.run()
        patched_run.assert_not_called()


@pytest.mark.unit
class TestConfigureLogging:
    """Tests for _configure_logging() covering both LOG_FORMAT branches."""

    def test_plaintext_branch_uses_basicconfig(self):
        """Absent LOG_FORMAT installs the plaintext handler without error."""
        import main
        with patch.dict("os.environ", {}, clear=False):
            # Remove LOG_FORMAT if present so the else-branch runs.
            env_without = {k: v for k, v in __import__("os").environ.items() if k != "LOG_FORMAT"}
            with patch.dict("os.environ", env_without, clear=True):
                with patch("logging.basicConfig") as mock_basicconfig:
                    main._configure_logging()
        mock_basicconfig.assert_called_once()
        call_kwargs = mock_basicconfig.call_args.kwargs
        assert call_kwargs.get("level") == logging.INFO
        assert "%(asctime)s" in call_kwargs.get("format", "")

    def test_json_branch_installs_json_formatter(self):
        """LOG_FORMAT=json installs a StreamHandler with a JSON formatter."""
        import main
        with patch.dict("os.environ", {"LOG_FORMAT": "json"}, clear=False):
            with patch("logging.basicConfig") as mock_basicconfig:
                main._configure_logging()
        mock_basicconfig.assert_called_once()
        call_kwargs = mock_basicconfig.call_args.kwargs
        assert call_kwargs.get("level") == logging.INFO
        assert call_kwargs.get("force") is True
        handlers = call_kwargs.get("handlers", [])
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_json_formatter_produces_valid_json(self):
        """The custom _JsonFormatter serialises a log record to valid JSON."""
        import main
        with patch.dict("os.environ", {"LOG_FORMAT": "json"}, clear=False):
            # Capture the handler that gets registered so we can test the formatter.
            captured_handlers: list = []

            def capture_basicconfig(**kwargs):
                captured_handlers.extend(kwargs.get("handlers", []))

            with patch("logging.basicConfig", side_effect=capture_basicconfig):
                main._configure_logging()

        assert captured_handlers, "No handler was captured"
        formatter = captured_handlers[0].formatter
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello world"
        assert "timestamp" in parsed

    def test_json_formatter_includes_extra_fields(self):
        """Extra fields passed to logger.info are merged into the JSON payload."""
        import main
        with patch.dict("os.environ", {"LOG_FORMAT": "json"}, clear=False):
            captured_handlers: list = []

            def capture_basicconfig(**kwargs):
                captured_handlers.extend(kwargs.get("handlers", []))

            with patch("logging.basicConfig", side_effect=capture_basicconfig):
                main._configure_logging()

        formatter = captured_handlers[0].formatter
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="audit",
            args=(),
            exc_info=None,
        )
        record.session_id = "abc-123"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed.get("session_id") == "abc-123"

    def test_json_branch_case_insensitive(self):
        """LOG_FORMAT=JSON (uppercase) also activates the JSON branch."""
        import main
        with patch.dict("os.environ", {"LOG_FORMAT": "JSON"}, clear=False):
            with patch("logging.basicConfig") as mock_basicconfig:
                main._configure_logging()
        call_kwargs = mock_basicconfig.call_args.kwargs
        assert call_kwargs.get("force") is True

    def test_main_guard_calls_run(self):
        """The if __name__ == '__main__' guard invokes run() without error."""
        import runpy
        mock_agent = MagicMock()
        with patch("age_calculator.create_agent", return_value=mock_agent):
            with patch("builtins.input", return_value="1990-01-01"):
                # run_module re-executes the source; run() must complete cleanly.
                runpy.run_module("main", run_name="__main__", alter_sys=False)
        mock_agent.assert_called_once()

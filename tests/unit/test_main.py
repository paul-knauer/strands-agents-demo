"""Unit tests for the main.py CLI entry point."""

import pathlib
import runpy
import sys
import pytest
from unittest.mock import MagicMock, patch

# Resolve main.py relative to this file's repo root (tests/ -> project root).
_MAIN_PATH = str(pathlib.Path(__file__).parent.parent.parent / "main.py")


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
class TestRunOutputMessages:
    """Verify the exact text that run() prints so users receive clear guidance."""

    def test_prints_welcome_message_on_valid_input(self, patched_run, capsys):
        with patch("builtins.input", return_value="1990-05-15"):
            import main
            main.run()
        captured = capsys.readouterr()
        assert "Welcome" in captured.out

    def test_error_message_contains_format_hint(self, patched_run, capsys):
        """Error message must contain 'YYYY-MM-DD' so the user knows the expected format."""
        with patch("builtins.input", return_value="not-a-date"):
            with pytest.raises(SystemExit):
                import main
                main.run()
        captured = capsys.readouterr()
        assert "YYYY-MM-DD" in captured.out

    def test_error_message_contains_invalid_date_value(self, patched_run, capsys):
        """Error message must echo the user's bad input so they can see what was wrong."""
        bad = "31/12/1990"
        with patch("builtins.input", return_value=bad):
            with pytest.raises(SystemExit):
                import main
                main.run()
        captured = capsys.readouterr()
        assert bad in captured.out


@pytest.mark.unit
class TestRunInvalidCalendarDates:
    """Dates that are syntactically YYYY-MM-DD but calendar-invalid must also exit(1)."""

    def test_non_leap_year_feb_29_exits_with_code_1(self, patched_run):
        """2023-02-29 is not a real date — must be rejected at the CLI level."""
        with patch("builtins.input", return_value="2023-02-29"):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1

    def test_non_leap_year_feb_29_does_not_invoke_agent(self, patched_run):
        with patch("builtins.input", return_value="2023-02-29"):
            with pytest.raises(SystemExit):
                import main
                main.run()
        patched_run.assert_not_called()

    def test_invalid_month_13_exits_with_code_1(self, patched_run):
        with patch("builtins.input", return_value="2024-13-01"):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1

    def test_invalid_day_32_exits_with_code_1(self, patched_run):
        with patch("builtins.input", return_value="2024-01-32"):
            with pytest.raises(SystemExit) as exc_info:
                import main
                main.run()
        assert exc_info.value.code == 1


@pytest.mark.unit
class TestRunPromptFormat:
    """The birthdate string passed to the agent must follow a predictable template."""

    def test_agent_called_with_my_birthdate_is_prefix(self, patched_run):
        """run() constructs the agent prompt as 'My birthdate is {date}...'."""
        with patch("builtins.input", return_value="1990-05-15"):
            import main
            main.run()
        call_args = patched_run.call_args[0][0]
        assert call_args.startswith("My birthdate is")

    def test_agent_prompt_asks_how_many_days_old(self, patched_run):
        """The agent prompt must ask 'How many days old am I?' to trigger the tool chain."""
        with patch("builtins.input", return_value="1990-05-15"):
            import main
            main.run()
        call_args = patched_run.call_args[0][0]
        assert "days old" in call_args.lower()


@pytest.mark.unit
class TestMainGuard:
    """The ``if __name__ == '__main__': run()`` guard must call run() when executed directly.

    ``runpy.run_path`` executes the script file with ``__name__`` set to
    ``'__main__'``, which is the only reliable way to cover the guard line
    without actually spawning a subprocess.
    """

    def test_main_guard_calls_run_when_executed_as_script(self):
        """Simulate ``python main.py`` — the __main__ guard must invoke run()."""
        mock_agent = MagicMock()
        with patch("age_calculator.create_agent", return_value=mock_agent), \
             patch("builtins.input", return_value="1990-05-15"):
            runpy.run_path(_MAIN_PATH, run_name="__main__")
        mock_agent.assert_called_once()

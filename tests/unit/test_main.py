"""Unit tests for the main.py CLI entry point."""

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

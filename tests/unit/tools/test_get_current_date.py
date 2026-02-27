"""Unit tests for the get_current_date tool."""

import datetime
import pytest

from age_calculator.tools import get_current_date


@pytest.mark.unit
class TestGetCurrentDate:
    def test_returns_string(self):
        result = get_current_date()
        assert isinstance(result, str)

    def test_format_is_iso(self):
        result = get_current_date()
        # Must parse without raising
        parsed = datetime.date.fromisoformat(result)
        assert isinstance(parsed, datetime.date)

    def test_matches_today(self):
        result = get_current_date()
        assert result == datetime.date.today().isoformat()

    def test_format_has_dashes(self):
        result = get_current_date()
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # YYYY
        assert len(parts[1]) == 2  # MM
        assert len(parts[2]) == 2  # DD

    # --- docstring contract (the model reads this) ---

    def test_docstring_exists(self):
        assert get_current_date.__doc__ is not None
        assert len(get_current_date.__doc__) > 50

    def test_docstring_contains_use_this_tool(self):
        assert "Use this tool" in get_current_date.__doc__

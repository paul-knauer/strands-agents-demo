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

    def test_docstring_mentions_return_format(self):
        """Docstring must tell the model what format the returned date string uses."""
        assert "YYYY-MM-DD" in get_current_date.__doc__

    # --- return value sanity (runs against real system clock) ---

    def test_year_is_plausible(self):
        """Year component must be in a realistic range for a live system."""
        result = get_current_date()
        year = int(result.split("-")[0])
        assert 2020 <= year <= 2100, f"Year {year} is outside the expected plausible range."

    def test_month_is_in_valid_range(self):
        result = get_current_date()
        month = int(result.split("-")[1])
        assert 1 <= month <= 12, f"Month {month} is not a valid month number."

    def test_day_is_in_valid_range(self):
        result = get_current_date()
        day = int(result.split("-")[2])
        assert 1 <= day <= 31, f"Day {day} is not a valid day number."

    # --- tool_spec contract (what the model sees) ---

    def test_tool_spec_name_matches_function_name(self):
        """tool_spec name is used by the Strands SDK as the tool identifier sent to Bedrock."""
        assert get_current_date.tool_spec["name"] == "get_current_date"

    def test_tool_spec_description_is_non_empty(self):
        assert len(get_current_date.tool_spec["description"].strip()) > 50

    def test_tool_spec_input_schema_has_no_required_params(self):
        """get_current_date takes no arguments — the schema must not list any required fields."""
        schema = get_current_date.tool_spec["inputSchema"]["json"]
        required = schema.get("required")
        assert not required, (
            f"get_current_date tool_spec lists required params: {required}. "
            "The tool takes no arguments."
        )

    def test_tool_spec_input_schema_has_no_properties(self):
        """Zero-argument tool must have an empty properties dict in the input schema."""
        props = get_current_date.tool_spec["inputSchema"]["json"].get("properties", {})
        assert props == {}, f"Expected empty properties, got: {props}"

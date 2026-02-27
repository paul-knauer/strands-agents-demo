"""Unit tests for the calculate_days_between tool."""

import pytest

from age_calculator.tools import calculate_days_between


@pytest.mark.unit
class TestCalculateDaysBetweenHappyPath:
    def test_known_span(self):
        # 1990-01-01 to 2000-01-01 = exactly 3652 days (1990s included leap years 1992, 1996)
        assert calculate_days_between("1990-01-01", "2000-01-01") == 3652

    def test_same_date_returns_zero(self):
        assert calculate_days_between("2000-06-15", "2000-06-15") == 0

    def test_consecutive_dates_returns_one(self):
        assert calculate_days_between("2024-03-01", "2024-03-02") == 1

    def test_leap_year_feb_28_to_mar_01(self):
        # 2024 is a leap year — Feb 28 to Mar 1 is 2 days
        assert calculate_days_between("2024-02-28", "2024-03-01") == 2

    def test_non_leap_year_feb_28_to_mar_01(self):
        # 2023 is not a leap year — Feb 28 to Mar 1 is 1 day
        assert calculate_days_between("2023-02-28", "2023-03-01") == 1

    def test_large_span_century(self):
        # 1900-01-01 to 2000-01-01 = 36524 days (century not a leap year)
        assert calculate_days_between("1900-01-01", "2000-01-01") == 36524

    def test_return_type_is_int(self):
        result = calculate_days_between("2000-01-01", "2000-12-31")
        assert isinstance(result, int)

    def test_return_value_is_non_negative(self):
        result = calculate_days_between("1990-05-15", "2024-01-01")
        assert result >= 0


@pytest.mark.unit
class TestCalculateDaysBetweenStartDateValidation:
    def test_empty_start_date_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("", "2024-01-01")

    def test_wrong_separator_start_date_raises(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("1990/01/01", "2024-01-01")
        assert "start_date" in str(exc_info.value)

    def test_non_date_string_start_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("hello", "2024-01-01")

    def test_partial_date_start_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("1990-01", "2024-01-01")

    def test_datetime_with_time_start_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01T00:00:00", "2024-01-01")

    def test_error_message_names_start_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("not-a-date", "2024-01-01")
        assert "start_date" in str(exc_info.value)


@pytest.mark.unit
class TestCalculateDaysBetweenEndDateValidation:
    def test_empty_end_date_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "")

    def test_wrong_separator_end_date_raises(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("1990-01-01", "2024/01/01")
        assert "end_date" in str(exc_info.value)

    def test_non_date_string_end_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "tomorrow")

    def test_partial_date_end_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "2024-01")

    def test_error_message_names_end_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("1990-01-01", "not-a-date")
        assert "end_date" in str(exc_info.value)


@pytest.mark.unit
class TestCalculateDaysBetweenOrderingConstraint:
    def test_start_after_end_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("2024-01-02", "2024-01-01")

    def test_start_one_day_after_end_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("2000-12-31", "2000-12-30")

    def test_error_message_contains_both_dates(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("2024-06-15", "2024-06-14")
        msg = str(exc_info.value)
        assert "2024-06-15" in msg
        assert "2024-06-14" in msg


@pytest.mark.unit
class TestCalculateDaysBetweenStartDateInvalidCalendar:
    """Dates that are syntactically ISO-like but calendar-invalid must raise."""

    def test_non_leap_year_feb_29_start_raises(self):
        """2023 is not a leap year — Feb 29 is not a valid calendar date."""
        with pytest.raises(ValueError):
            calculate_days_between("2023-02-29", "2024-01-01")

    def test_non_leap_year_feb_29_start_error_names_start_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("2023-02-29", "2024-01-01")
        assert "start_date" in str(exc_info.value)

    def test_century_non_leap_feb_29_start_raises(self):
        """1900 is divisible by 100 but not 400 — not a leap year."""
        with pytest.raises(ValueError):
            calculate_days_between("1900-02-29", "2024-01-01")

    def test_invalid_month_13_start_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("2024-13-01", "2024-12-31")

    def test_invalid_month_13_start_error_names_start_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("2024-13-01", "2024-12-31")
        assert "start_date" in str(exc_info.value)

    def test_reversed_date_format_start_raises(self):
        """DD-MM-YYYY is not ISO 8601 — tool must reject it."""
        with pytest.raises(ValueError):
            calculate_days_between("01-01-1990", "2024-01-01")


@pytest.mark.unit
class TestCalculateDaysBetweenEndDateInvalidCalendar:
    """Dates that are syntactically ISO-like but calendar-invalid must raise."""

    def test_non_leap_year_feb_29_end_raises(self):
        """2023 is not a leap year — Feb 29 is not a valid calendar date."""
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "2023-02-29")

    def test_non_leap_year_feb_29_end_error_names_end_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("1990-01-01", "2023-02-29")
        assert "end_date" in str(exc_info.value)

    def test_century_non_leap_feb_29_end_raises(self):
        """1900 is divisible by 100 but not 400 — not a leap year."""
        with pytest.raises(ValueError):
            calculate_days_between("1890-01-01", "1900-02-29")

    def test_invalid_month_0_end_raises(self):
        with pytest.raises(ValueError):
            calculate_days_between("2024-01-01", "2024-00-15")

    def test_invalid_month_0_end_error_names_end_date(self):
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("2024-01-01", "2024-00-15")
        assert "end_date" in str(exc_info.value)

    def test_datetime_with_time_end_raises(self):
        """A datetime string (with T separator) must not be accepted as end_date."""
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "2024-06-01T00:00:00")

    def test_reversed_date_format_end_raises(self):
        """DD-MM-YYYY is not ISO 8601 — tool must reject it."""
        with pytest.raises(ValueError):
            calculate_days_between("1990-01-01", "01-01-2025")


@pytest.mark.unit
class TestCalculateDaysBetweenBoundaryValues:
    """Boundary dates the tool must handle without error."""

    def test_leap_year_400_feb_29_is_valid(self):
        """2000 is divisible by 400 — Feb 29 is a valid calendar date."""
        result = calculate_days_between("2000-02-29", "2000-03-01")
        assert result == 1

    def test_max_valid_date_same_start_end(self):
        """9999-12-31 is the maximum ISO date; same start/end returns 0."""
        assert calculate_days_between("9999-12-31", "9999-12-31") == 0

    def test_first_day_of_year_to_last_non_leap(self):
        """2023 has 365 days."""
        assert calculate_days_between("2023-01-01", "2023-12-31") == 364

    def test_first_day_of_year_to_last_leap(self):
        """2024 has 366 days."""
        assert calculate_days_between("2024-01-01", "2024-12-31") == 365


@pytest.mark.unit
class TestCalculateDaysBetweenToolSpec:
    """The tool_spec JSON fed to the model must be structurally correct.

    The Strands SDK sends ``tool_spec`` verbatim to the Bedrock API.  If the
    schema is malformed the model may misinterpret the tool signature, leading
    to incorrect parameter extraction.
    """

    def test_tool_spec_name_matches_function_name(self):
        assert calculate_days_between.tool_spec["name"] == "calculate_days_between"

    def test_tool_spec_description_is_non_empty(self):
        assert len(calculate_days_between.tool_spec["description"].strip()) > 50

    def test_tool_spec_input_schema_has_start_date_property(self):
        props = calculate_days_between.tool_spec["inputSchema"]["json"]["properties"]
        assert "start_date" in props

    def test_tool_spec_input_schema_has_end_date_property(self):
        props = calculate_days_between.tool_spec["inputSchema"]["json"]["properties"]
        assert "end_date" in props

    def test_tool_spec_start_date_type_is_string(self):
        props = calculate_days_between.tool_spec["inputSchema"]["json"]["properties"]
        assert props["start_date"]["type"] == "string"

    def test_tool_spec_end_date_type_is_string(self):
        props = calculate_days_between.tool_spec["inputSchema"]["json"]["properties"]
        assert props["end_date"]["type"] == "string"

    def test_tool_spec_both_params_are_required(self):
        required = calculate_days_between.tool_spec["inputSchema"]["json"]["required"]
        assert "start_date" in required
        assert "end_date" in required

    def test_tool_spec_no_extra_required_params(self):
        required = set(calculate_days_between.tool_spec["inputSchema"]["json"]["required"])
        assert required == {"start_date", "end_date"}


@pytest.mark.unit
class TestCalculateDaysBetweenDocstring:
    def test_docstring_exists(self):
        assert calculate_days_between.__doc__ is not None
        assert len(calculate_days_between.__doc__) > 50

    def test_docstring_contains_use_this_tool(self):
        assert "Use this tool" in calculate_days_between.__doc__

    def test_docstring_documents_start_date_param(self):
        assert "start_date" in calculate_days_between.__doc__

    def test_docstring_documents_end_date_param(self):
        assert "end_date" in calculate_days_between.__doc__

    def test_docstring_mentions_raises_value_error(self):
        """Docstring must document the ValueError so the model knows tool errors are possible."""
        assert "ValueError" in calculate_days_between.__doc__

    def test_docstring_mentions_yyyy_mm_dd_format(self):
        """Docstring must state the expected date format so the model supplies it correctly."""
        assert "YYYY-MM-DD" in calculate_days_between.__doc__

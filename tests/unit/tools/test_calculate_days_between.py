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

    def test_error_message_does_not_echo_raw_dates(self):
        # SEC-012: error messages must not reflect raw user input (reflected content injection)
        with pytest.raises(ValueError) as exc_info:
            calculate_days_between("2024-06-15", "2024-06-14")
        msg = str(exc_info.value)
        assert "start_date" in msg
        assert "2024-06-15" not in msg
        assert "2024-06-14" not in msg


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

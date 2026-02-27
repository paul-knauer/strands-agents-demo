"""Strands tools for date arithmetic used by the age calculator agent.

Each function is decorated with ``@tool`` so the Strands framework can
expose it to the language model.  Input validation is performed before any
computation so that the model receives a clear error message rather than a
cryptic Python traceback.
"""

import datetime
import logging

from strands import tool

logger: logging.Logger = logging.getLogger(__name__)


@tool
def get_current_date() -> str:
    """Get today's date in YYYY-MM-DD format.

    Use this tool to retrieve the current date when you need to calculate
    how many days old someone is based on their birthdate.

    Returns:
        Today's date as a string in YYYY-MM-DD format.
    """
    today = datetime.date.today().isoformat()
    logger.debug("get_current_date called, returning %s", today)
    return today


@tool
def calculate_days_between(start_date: str, end_date: str) -> int:
    """Calculate the number of days between two dates.

    Use this tool to compute the difference in days between a start date
    (e.g., a birthdate) and an end date (e.g., today's date).  The start
    date must be earlier than or equal to the end date.

    Args:
        start_date: The earlier date in YYYY-MM-DD format.
        end_date: The later date in YYYY-MM-DD format.

    Returns:
        The number of days between start_date and end_date as a
        non-negative integer.

    Raises:
        ValueError: If either date string is not in YYYY-MM-DD format, or
            if start_date is strictly after end_date.
    """
    # SEC-002: type, length, and range validation before any parsing
    _MAX_DATE_LEN = 10
    _MIN_DATE = datetime.date(1900, 1, 1)
    _MAX_DATE = datetime.date(2100, 12, 31)

    if not isinstance(start_date, str):
        raise ValueError("start_date must be a string.")
    if not isinstance(end_date, str):
        raise ValueError("end_date must be a string.")
    if len(start_date) > _MAX_DATE_LEN:
        raise ValueError(f"start_date exceeds maximum length of {_MAX_DATE_LEN}.")
    if len(end_date) > _MAX_DATE_LEN:
        raise ValueError(f"end_date exceeds maximum length of {_MAX_DATE_LEN}.")

    # SEC-013: log input lengths, not raw values
    logger.debug(
        "calculate_days_between called with %d-char start_date, %d-char end_date",
        len(start_date),
        len(end_date),
    )

    try:
        start = datetime.date.fromisoformat(start_date)
    except ValueError as exc:
        raise ValueError(
            "start_date is not a valid ISO date (YYYY-MM-DD)."
        ) from exc

    try:
        end = datetime.date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError(
            "end_date is not a valid ISO date (YYYY-MM-DD)."
        ) from exc

    if not (_MIN_DATE <= start <= _MAX_DATE):
        raise ValueError(f"start_date is outside the allowed range (1900-01-01 to 2100-12-31).")
    if not (_MIN_DATE <= end <= _MAX_DATE):
        raise ValueError(f"end_date is outside the allowed range (1900-01-01 to 2100-12-31).")

    if start > end:
        raise ValueError("start_date must not be after end_date.")

    days: int = (end - start).days
    logger.debug("calculate_days_between result: %d days", days)
    return days

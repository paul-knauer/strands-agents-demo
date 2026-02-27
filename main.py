"""Entry point for the age calculator CLI.

Run with:
    python main.py

The script configures structured logging, builds the agent, prompts the user
for their birthdate, validates the input, and then invokes the agent.
"""

import datetime
import json
import logging
import os
import sys

from age_calculator import create_agent
from age_calculator.agent import invoke_with_audit

logger: logging.Logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure logging format based on the LOG_FORMAT environment variable.

    Set LOG_FORMAT=json for structured JSON output (CloudWatch-friendly).
    Any other value (or absent) falls back to human-readable plaintext.
    """
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    if log_format == "json":
        class _JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload: dict[str, object] = {
                    "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                # Merge any extra fields passed via logger.info(..., extra={...})
                for key, value in record.__dict__.items():
                    if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                        payload[key] = value
                return json.dumps(payload)

        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )


def run() -> None:
    """Configure logging, build the agent, and run the interactive prompt.

    Validates the user-supplied birthdate with ``datetime.date.fromisoformat``
    before passing it to the agent.  Exits with code 1 on invalid input so
    that callers (shell scripts, Docker health checks, etc.) can detect
    failure cleanly.

    After a successful agent invocation a structured audit record is emitted
    via ``logger.info`` containing session_id, timestamp (ISO UTC),
    elapsed_ms, and the user input truncated to 100 characters.  The agent
    response is intentionally excluded from the audit log to avoid retaining
    PII.
    """
    _configure_logging()

    agent = create_agent()

    print("Welcome to the Age Calculator!")
    birthdate_raw = input("Please enter your birthdate (YYYY-MM-DD, e.g. 1990-05-15): ").strip()

    try:
        datetime.date.fromisoformat(birthdate_raw)
    except ValueError:
        # SEC-014: truncate echoed user input to prevent reflected content injection
        safe_input = birthdate_raw[:20]
        print(
            f"Error: '{safe_input}' is not a valid date. "
            "Please use the format YYYY-MM-DD (e.g. 1990-05-15)."
        )
        sys.exit(1)

    invoke_with_audit(agent, f"My birthdate is {birthdate_raw}. How many days old am I?")


if __name__ == "__main__":
    run()

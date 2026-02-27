"""Entry point for the age calculator CLI.

Run with:
    python main.py

The script configures structured logging, builds the agent, prompts the user
for their birthdate, validates the input, and then invokes the agent.
"""

import logging
import sys
from datetime import date

from age_calculator import create_agent
from age_calculator.agent import invoke_with_audit


def run() -> None:
    """Configure logging, build the agent, and run the interactive prompt.

    Validates the user-supplied birthdate with ``datetime.date.fromisoformat``
    before passing it to the agent.  Exits with code 1 on invalid input so
    that callers (shell scripts, Docker health checks, etc.) can detect
    failure cleanly.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    agent = create_agent()

    print("Welcome to the Age Calculator!")
    birthdate_raw = input("Please enter your birthdate (YYYY-MM-DD, e.g. 1990-05-15): ").strip()

    try:
        date.fromisoformat(birthdate_raw)
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

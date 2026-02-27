"""Smoke test for the deployed age_calculator agent package.

This script verifies that the agent package is importable and correctly
structured without making any live AWS / Bedrock API calls.  It is designed
to run in CI after a Docker image is built and in a deployment environment
after the container starts.

Usage
-----
    python scripts/smoke_test.py --environment staging
    python scripts/smoke_test.py --environment production

Exit codes
----------
0   All checks passed.
1   One or more checks failed.  A summary is printed to stdout.
"""

import argparse
import datetime
import importlib
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

# Ensure the project root is on sys.path so age_calculator is importable when
# the script is run directly (e.g. locally or in a Docker container that uses
# ENTRYPOINT rather than pip install).
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

VALID_ENVIRONMENTS: frozenset[str] = frozenset({"staging", "production"})


# ---------------------------------------------------------------------------
# Result accumulation
# ---------------------------------------------------------------------------

_results: list[tuple[str, bool, str]] = []


def _record(name: str, passed: bool, detail: str = "") -> bool:
    """Store a check result and print a one-line status.

    Args:
        name: Human-readable name for the check.
        passed: True if the check succeeded.
        detail: Optional extra context appended when the check fails.

    Returns:
        The value of ``passed``, so callers can use ``if not _record(...)``.
    """
    icon = "PASS" if passed else "FAIL"
    line = f"  [{icon}] {name}"
    if not passed and detail:
        line += f": {detail}"
    print(line)
    _results.append((name, passed, detail))
    return passed


def _run_check(name: str, fn: Callable[[], Any]) -> bool:
    """Execute ``fn``, catch any exception, and record the outcome.

    Args:
        name: Human-readable name for the check.
        fn: Zero-argument callable that raises on failure or returns a value.

    Returns:
        True if ``fn`` completed without raising, False otherwise.
    """
    try:
        fn()
        return _record(name, True)
    except Exception:  # noqa: BLE001 — we want to catch everything for smoke tests
        detail = traceback.format_exc().strip().splitlines()[-1]
        return _record(name, False, detail)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_package_importable() -> None:
    """Import the top-level age_calculator package."""
    importlib.import_module("age_calculator")


def check_create_agent_importable() -> None:
    """Import create_agent from age_calculator."""
    mod = importlib.import_module("age_calculator")
    assert hasattr(mod, "create_agent"), (
        "age_calculator does not export 'create_agent'"
    )


def check_create_agent_is_callable() -> None:
    """Verify that create_agent is a callable (factory function)."""
    mod = importlib.import_module("age_calculator")
    factory = getattr(mod, "create_agent")
    assert callable(factory), f"create_agent is not callable, got {type(factory)}"


def check_tools_importable() -> None:
    """Import both tools from age_calculator.tools."""
    mod = importlib.import_module("age_calculator.tools")
    assert hasattr(mod, "get_current_date"), (
        "age_calculator.tools does not export 'get_current_date'"
    )
    assert hasattr(mod, "calculate_days_between"), (
        "age_calculator.tools does not export 'calculate_days_between'"
    )


def check_get_current_date_returns_iso_date() -> None:
    """Call get_current_date() and verify it returns a valid ISO date string."""
    from age_calculator.tools import get_current_date  # type: ignore[attr-defined]

    # The @tool decorator wraps the function; call the underlying callable.
    # Strands tool objects expose the underlying function via __call__.
    result = get_current_date()
    assert isinstance(result, str), (
        f"get_current_date() returned {type(result).__name__}, expected str"
    )
    # Validate it is a parseable ISO date in YYYY-MM-DD format.
    parsed = datetime.date.fromisoformat(result)
    # Sanity check: the date must be plausible (year >= 2020).
    assert parsed.year >= 2020, (
        f"get_current_date() returned an unexpectedly old date: {result}"
    )


def check_calculate_days_between_result() -> None:
    """Call calculate_days_between('1990-01-01', '2000-01-01') and verify 3652."""
    from age_calculator.tools import calculate_days_between  # type: ignore[attr-defined]

    result = calculate_days_between("1990-01-01", "2000-01-01")
    assert result == 3652, (
        f"calculate_days_between('1990-01-01', '2000-01-01') returned {result}, expected 3652"
    )


def check_system_prompt_keywords() -> None:
    """Verify the system prompt contains the expected domain keywords."""
    from age_calculator.agent import SYSTEM_PROMPT  # type: ignore[attr-defined]

    required_keywords = ["age", "days", "birthdate", "calculate"]
    present = [kw for kw in required_keywords if kw.lower() in SYSTEM_PROMPT.lower()]
    assert len(present) >= 2, (
        f"SYSTEM_PROMPT must contain at least 2 of {required_keywords}, "
        f"found only {present!r}. Prompt: {SYSTEM_PROMPT!r}"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed namespace with ``environment`` (str).
    """
    parser = argparse.ArgumentParser(
        description="Smoke test the age_calculator agent package.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/smoke_test.py --environment staging\n"
            "  python scripts/smoke_test.py --environment production\n"
        ),
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=sorted(VALID_ENVIRONMENTS),
        help="Target environment label (staging or production).",
    )
    return parser.parse_args()


def main() -> None:
    """Run all smoke checks and exit with an appropriate code."""
    args = _parse_args()
    environment: str = args.environment

    print(f"\n[smoke_test] Running smoke tests against environment: {environment}\n")

    checks: list[tuple[str, Callable[[], Any]]] = [
        ("Import age_calculator package", check_package_importable),
        ("Import create_agent from age_calculator", check_create_agent_importable),
        ("create_agent is callable", check_create_agent_is_callable),
        ("Import tools from age_calculator.tools", check_tools_importable),
        ("get_current_date() returns valid ISO date", check_get_current_date_returns_iso_date),
        (
            "calculate_days_between('1990-01-01', '2000-01-01') == 3652",
            check_calculate_days_between_result,
        ),
        ("SYSTEM_PROMPT contains expected keywords", check_system_prompt_keywords),
    ]

    for name, fn in checks:
        _run_check(name, fn)

    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    print(f"\n[smoke_test] Results: {passed}/{total} checks passed.")

    if failed > 0:
        print(
            f"[smoke_test] FAIL: {failed} check(s) failed. "
            "See above for details.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[smoke_test] PASS: All checks passed for environment '{environment}'.")
    sys.exit(0)


if __name__ == "__main__":
    main()

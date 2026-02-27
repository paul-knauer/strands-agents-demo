"""Smoke test for the deployed age_calculator agent on AWS AgentCore.

This script runs two tiers of checks:

1. **Static checks** — verifies the agent package is importable and correctly
   structured.  These run unconditionally and require no AWS credentials.

2. **Live endpoint check** — invokes the live AgentCore agent runtime and
   asserts that the response is non-empty, contains the word "days", and
   contains at least one numeric character.  This check requires:
   - AWS credentials with ``bedrock-agentcore:InvokeAgentRuntime`` permission.
   - The ``AGENT_ID_STAGING`` or ``AGENT_ID_PRODUCTION`` environment variable
     (or the generic ``AGENT_ID`` fallback) set to the target AgentCore runtime
     ID for the chosen environment.

   The live check is skipped (with a warning) when no agent ID is available so
   that the static checks can still be used in environments without AWS access.

Usage
-----
    python scripts/smoke_test.py --environment staging
    python scripts/smoke_test.py --environment production

Exit codes
----------
0   All checks passed (or live check was skipped due to missing agent ID).
1   One or more checks failed.  A summary is printed to stdout.
"""

import argparse
import datetime
import importlib
import os
import sys
import time
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

# Maximum number of attempts for the live invocation (handles cold-start latency).
_LIVE_MAX_ATTEMPTS = 3
_LIVE_RETRY_DELAY_SECONDS = 5

# Prompt used for the live invocation smoke check.
_LIVE_PROMPT = "How many days old is someone born on 1990-01-01?"


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
# Static checks
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

    result = get_current_date()
    assert isinstance(result, str), (
        f"get_current_date() returned {type(result).__name__}, expected str"
    )
    parsed = datetime.date.fromisoformat(result)
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
# Live endpoint check
# ---------------------------------------------------------------------------

def _get_agent_id(environment: str) -> str | None:
    """Resolve the AgentCore runtime ID for the given environment.

    Checks (in order):
    1. ``AGENT_ID_<ENVIRONMENT>`` (e.g. ``AGENT_ID_STAGING``)
    2. ``AGENT_ID`` generic fallback

    Args:
        environment: The target environment label (``staging`` or ``production``).

    Returns:
        The agent runtime ID string, or ``None`` if not set.
    """
    env_specific = f"AGENT_ID_{environment.upper()}"
    return os.environ.get(env_specific) or os.environ.get("AGENT_ID") or None


def _invoke_agent_runtime(agent_id: str, region: str, prompt: str) -> str:
    """Invoke an AgentCore runtime and return the response text.

    Args:
        agent_id: The AgentCore runtime ID.
        region: AWS region.
        prompt: User prompt to send.

    Returns:
        The response content as a plain string.

    Raises:
        RuntimeError: If the invocation fails or returns an empty response.
    """
    import boto3  # type: ignore[import-untyped]
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

    client = boto3.client("bedrock-agentcore", region_name=region)
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeId=agent_id,
            payload={"inputText": prompt},
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"AgentCore invocation failed: {exc}") from exc

    # The response payload is a streaming body; read it fully.
    body = response.get("body") or response.get("outputText") or ""
    if hasattr(body, "read"):
        body = body.read().decode("utf-8")

    if not body:
        raise RuntimeError("AgentCore returned an empty response body.")

    return body


def run_live_endpoint_check(environment: str) -> None:
    """Invoke the live AgentCore endpoint and validate the response.

    Retries up to ``_LIVE_MAX_ATTEMPTS`` times with a delay to handle
    cold-start latency before recording a failure.

    Args:
        environment: Target environment label (``staging`` or ``production``).
    """
    agent_id = _get_agent_id(environment)
    if not agent_id:
        env_var = f"AGENT_ID_{environment.upper()}"
        print(
            f"\n  [SKIP] Live endpoint check: neither {env_var!r} nor AGENT_ID "
            "is set.  Set the environment variable to enable this check."
        )
        return

    region = os.environ.get("AWS_REGION", "us-east-1")
    check_name = f"Live AgentCore invocation ({environment})"

    last_error: str = ""
    for attempt in range(1, _LIVE_MAX_ATTEMPTS + 1):
        try:
            response_text = _invoke_agent_runtime(agent_id, region, _LIVE_PROMPT)

            # Validate response content.
            assert response_text.strip(), "Response is blank."
            lower = response_text.lower()
            assert "days" in lower, (
                f"Response does not contain the word 'days'. Got: {response_text!r}"
            )
            assert any(ch.isdigit() for ch in response_text), (
                f"Response contains no numeric characters. Got: {response_text!r}"
            )

            _record(check_name, True)
            return

        except Exception:  # noqa: BLE001
            last_error = traceback.format_exc().strip().splitlines()[-1]
            if attempt < _LIVE_MAX_ATTEMPTS:
                print(
                    f"  [RETRY] Live check attempt {attempt}/{_LIVE_MAX_ATTEMPTS} failed "
                    f"({last_error}). Retrying in {_LIVE_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(_LIVE_RETRY_DELAY_SECONDS)

    _record(check_name, False, f"All {_LIVE_MAX_ATTEMPTS} attempts failed. Last error: {last_error}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed namespace with ``environment`` (str).
    """
    parser = argparse.ArgumentParser(
        description="Smoke test the age_calculator agent on AWS AgentCore.",
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

    static_checks: list[tuple[str, Callable[[], Any]]] = [
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

    for name, fn in static_checks:
        _run_check(name, fn)

    # Live endpoint check — requires AWS credentials and AGENT_ID_* env var.
    run_live_endpoint_check(environment)

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

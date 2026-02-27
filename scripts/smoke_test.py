"""Post-deployment smoke test for the Age Calculator agent on AWS AgentCore.

Validates that the deployed agent endpoint is reachable and returns a
plausible response for a canonical age-in-days query.  Exits non-zero on
any failure so the pipeline can roll back automatically.

The AgentCore runtime exposes agents via the Bedrock AgentCore API.  This
script invokes the agent using the boto3 bedrock-agentcore client and
asserts on the response content.

Environment variables (required)
---------------------------------
AGENT_ID
    The AgentCore agent ID for the target environment.
    Populated automatically by the CDK stack outputs or set manually.

AWS credentials must be available via the standard boto3 credential chain
(instance profile / OIDC role assumption in CI).

Usage::

    python scripts/smoke_test.py --environment staging
    python scripts/smoke_test.py --environment production
    python scripts/smoke_test.py --environment staging --region eu-west-1
"""

import argparse
import os
import sys
import time
from typing import Any

CANONICAL_INPUT = "My birthdate is 1990-05-15. How many days old am I?"

# Substrings that must appear in the agent's response for the smoke test to
# pass.  We check for a number (the day count) and the word "days".
REQUIRED_RESPONSE_SUBSTRINGS = ["days"]

# Maximum time in seconds to wait for the agent to respond.
REQUEST_TIMEOUT_SECONDS = 30

# Number of retries on transient failures (e.g. cold-start latency).
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def _get_agent_id(environment: str) -> str:
    """Resolve the AgentCore agent ID from environment variables."""
    env_var = f"AGENT_ID_{environment.upper()}"
    agent_id = os.environ.get(env_var) or os.environ.get("AGENT_ID")
    if not agent_id:
        print(
            f"ERROR: AgentCore agent ID not found.\n"
            f"Set the '{env_var}' or 'AGENT_ID' environment variable to the "
            f"AgentCore agent ID for the {environment} environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    return agent_id


def _invoke_agent(agent_id: str, region: str, user_input: str) -> str:
    """Invoke the AgentCore agent and return the full text response.

    Uses the bedrock-agentcore boto3 client.  Streams the response and
    concatenates all text chunks into a single string.
    """
    try:
        import boto3
    except ImportError:
        print(
            "ERROR: boto3 is not installed. Run 'pip install boto3'.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = boto3.client("bedrock-agentcore", region_name=region)

    response: Any = client.invoke_agent_runtime(
        agentId=agent_id,
        inputText=user_input,
    )

    # The response body is a streaming EventStream.  Collect all text chunks.
    output_text = ""
    event_stream = response.get("completion") or response.get("outputText") or response
    if hasattr(event_stream, "__iter__"):
        for event in event_stream:
            chunk = event.get("chunk", {})
            if "bytes" in chunk:
                output_text += chunk["bytes"].decode("utf-8")
    elif isinstance(response, dict):
        output_text = (
            response.get("outputText", "")
            or response.get("completion", "")
            or str(response)
        )

    return output_text.strip()


def _run_smoke_test(environment: str, region: str) -> bool:
    """Run the smoke test.  Returns True on pass, False on fail."""
    agent_id = _get_agent_id(environment)

    print(f"Smoke test: environment={environment} region={region} agent_id={agent_id}")
    print(f"Input: {CANONICAL_INPUT!r}")

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response_text = _invoke_agent(agent_id, region, CANONICAL_INPUT)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(
                f"Attempt {attempt}/{MAX_RETRIES} failed: {exc}",
                file=sys.stderr,
            )
            if attempt < MAX_RETRIES:
                print(f"Retrying in {RETRY_DELAY_SECONDS}s ...", file=sys.stderr)
                time.sleep(RETRY_DELAY_SECONDS)
    else:
        print(
            f"ERROR: All {MAX_RETRIES} attempts failed. Last error: {last_error}",
            file=sys.stderr,
        )
        return False

    print(f"Response: {response_text!r}")

    # Assert response is non-empty.
    if not response_text:
        print("FAIL: Agent returned an empty response.", file=sys.stderr)
        return False

    # Assert required substrings are present.
    missing = [s for s in REQUIRED_RESPONSE_SUBSTRINGS if s.lower() not in response_text.lower()]
    if missing:
        print(
            f"FAIL: Response missing required substrings: {missing}\n"
            f"Full response: {response_text!r}",
            file=sys.stderr,
        )
        return False

    # Assert the response contains at least one number (the day count).
    if not any(char.isdigit() for char in response_text):
        print(
            f"FAIL: Response contains no numeric day count.\n"
            f"Full response: {response_text!r}",
            file=sys.stderr,
        )
        return False

    print(f"PASS: Smoke test passed for {environment}.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-deployment smoke test for the Age Calculator AgentCore agent."
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=["staging", "production"],
        help="Target deployment environment.",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region where the agent is deployed (default: us-east-1).",
    )
    args = parser.parse_args()

    passed = _run_smoke_test(args.environment, args.region)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

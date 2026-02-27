"""Roll back an AgentCore alias to a specific known-good version.

Updates the routing configuration on a Bedrock AgentCore alias so that 100%
of traffic is directed to the nominated target version.  Exits non-zero on
any failure so the caller (CI job or operator) can detect and escalate.

Usage::

    python scripts/rollback_alias.py \\
        --agent-id  <agentcore-runtime-id> \\
        --alias-id  <agentcore-alias-id> \\
        --target-version <version-string>

Example::

    python scripts/rollback_alias.py \\
        --agent-id  abc123def456 \\
        --alias-id  TSTALIASID \\
        --target-version 2

AWS credentials must be available via the standard boto3 credential chain
(OIDC role assumption in CI, instance profile on EC2, or environment variables
for local operator use).  The caller must hold the
``bedrock-agentcore:UpdateAgentRuntimeAlias`` permission on the target alias
ARN.
"""

import argparse
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def rollback(agent_id: str, alias_id: str, target_version: str, region: str) -> None:
    """Update *alias_id* on *agent_id* to route 100% of traffic to *target_version*.

    Raises ``SystemExit(1)`` on any AWS or network error so that the pipeline
    receives a non-zero exit code and can block or alert automatically.
    """
    client = boto3.client("bedrock-agentcore", region_name=region)

    print(
        f"Rolling back alias '{alias_id}' on agent '{agent_id}' "
        f"to version '{target_version}' in region '{region}' ..."
    )

    try:
        response = client.update_agent_runtime_alias(
            agentRuntimeId=agent_id,
            agentRuntimeAliasId=alias_id,
            routingConfiguration=[
                {
                    "agentRuntimeVersion": target_version,
                    "routingCriteria": {"percentage": 100},
                }
            ],
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        print(
            f"ERROR: AWS API call failed — {error_code}: {error_msg}",
            file=sys.stderr,
        )
        sys.exit(1)
    except BotoCoreError as exc:
        print(f"ERROR: boto3 error — {exc}", file=sys.stderr)
        sys.exit(1)

    alias_arn = response.get("agentRuntimeAliasArn", "<unknown ARN>")
    print(
        f"SUCCESS: Alias '{alias_id}' (ARN: {alias_arn}) "
        f"now routes 100% of traffic to version '{target_version}'."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Roll back a Bedrock AgentCore alias to a specific known-good version. "
            "Sets the alias routing configuration to 100% of traffic on the target version."
        )
    )
    parser.add_argument(
        "--agent-id",
        required=True,
        help="The AgentCore runtime ID (agentRuntimeId) of the agent to update.",
    )
    parser.add_argument(
        "--alias-id",
        required=True,
        help="The alias ID (agentRuntimeAliasId) to update.",
    )
    parser.add_argument(
        "--target-version",
        required=True,
        help="The version string to roll back to (e.g. '2' or 'v1.4.2').",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region where the AgentCore runtime is deployed (default: us-east-1).",
    )
    args = parser.parse_args()

    rollback(
        agent_id=args.agent_id,
        alias_id=args.alias_id,
        target_version=args.target_version,
        region=args.region,
    )


if __name__ == "__main__":
    main()

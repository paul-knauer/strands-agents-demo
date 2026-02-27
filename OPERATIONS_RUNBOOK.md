# Operations Runbook — nCino Banking Agent on AWS AgentCore

**Project:** nCino-AgentCore
**Cost Centre:** PDE-Africa
**Maintainer:** Platform Engineering

---

## Table of Contents

1. [Standard Deploy Procedure](#1-standard-deploy-procedure)
2. [Rollback Procedure](#2-rollback-procedure)
3. [Incident Response Checklist](#3-incident-response-checklist)
4. [Running Smoke Tests Manually](#4-running-smoke-tests-manually)
5. [Environment Variable Reference](#5-environment-variable-reference)

---

## 1. Standard Deploy Procedure

### How CI/CD Works

Every push to `main` or `develop` triggers the GitHub Actions workflow defined in `.github/workflows/agent-deploy.yml`. The pipeline has seven ordered stages that must all pass before production is updated. No stage may be skipped or reordered.

```
validate -> unit-test -> integration-test -> evaluate -> build-and-scan -> deploy-staging -> deploy-production
```

### Stage Descriptions

**validate**
Runs on every push and pull request. Installs Python dev dependencies, then:
- Lints the `age_calculator/` package with `ruff`.
- Type-checks with `mypy --strict`.
- Installs CDK Node dependencies and runs `cdk synth`, piping the CloudFormation output through `cfn-lint` to catch template errors before any AWS call is made.

**unit-test**
Runs the `tests/unit/` suite with `pytest`, requiring 90% code coverage. Results are uploaded as a build artefact even on failure so engineers can inspect them without re-running the pipeline.

**integration-test**
Runs the `tests/integration/` suite. These tests construct a real `strands.Agent` instance with the AWS model replaced by a mock, verifying that `create_agent()` wires all components correctly without making live API calls.

**evaluate**
Runs the `tests/evaluation/` suite to assess AI quality. After the pytest run, two threshold gates are enforced via `scripts/check_threshold.py`:
- `tool_selection` must be >= 0.95 (95%).
- `refusal_accuracy` must be 1.00 (100%, zero tolerance for safety misses).

The pipeline fails immediately if either threshold is not met.

**build-and-scan**
Builds the Docker image with the immutable git SHA as the tag (`ECR_REPOSITORY:${{ github.sha }}`). Scans the image with Trivy for HIGH and CRITICAL CVEs before pushing. If Trivy finds any vulnerabilities at those severities, the stage fails and the image is never pushed to ECR. On a clean scan the image is pushed to ECR so that downstream deployment stages pull the already-verified image without rebuilding.

**deploy-staging**
Requires the `staging` GitHub Actions environment (configured in the repository settings). Assumes the `AWS_STAGING_ROLE_ARN` OIDC role, pulls the already-built image from ECR, re-tags it for staging, and deploys the CDK stack `AgentStack/Staging`. Runs `scripts/smoke_test.py --environment staging` at the end.

**deploy-production**
Only runs on pushes to `main`. Requires the `production` GitHub Actions environment, which has a manual approval gate configured in GitHub. A designated approver must review the staging smoke test results and click Approve before this stage starts. Deploys `AgentStack/Production` and runs `scripts/smoke_test.py --environment production`.

### Branching Model

| Branch    | Triggers                              |
|-----------|---------------------------------------|
| `main`    | Full pipeline including production    |
| `develop` | All stages except deploy-production   |
| PR to `main` | validate + unit-test only (no deploy) |

---

## 2. Rollback Procedure

### When to Trigger a Rollback

Trigger a rollback when any of the following occur after a production deploy:

- The `ncino-banking-agent-production-error-count` CloudWatch alarm fires.
- Smoke test passes in CI but live user traffic returns errors or incorrect responses.
- A critical CVE is discovered in the deployed image after it was promoted.
- A model version update introduces a regression in tool selection or refusal accuracy.

### Who Approves a Rollback

Production rollbacks must be approved by either:
- The on-call Platform Engineer, or
- An Engineering Manager from the PDE-Africa team.

For staging rollbacks no approval is required; any engineer on the team can execute one.

### Exact Rollback Command

```bash
python scripts/rollback_alias.py \
    --agent-id  <AGENTCORE_RUNTIME_ID> \
    --alias-id  <AGENTCORE_ALIAS_ID> \
    --target-version <PREVIOUS_GOOD_VERSION> \
    --region us-east-1
```

**Example — rolling production back to version 2:**

```bash
python scripts/rollback_alias.py \
    --agent-id  abc123def456 \
    --alias-id  PRODALIASID \
    --target-version 2 \
    --region us-east-1
```

The script exits `0` on success and non-zero on any AWS API failure, making it safe to call from CI or from the operator's terminal. The required AWS permission is `bedrock-agentcore:UpdateAgentRuntimeAlias` on the target alias ARN.

### Prerequisites

AWS credentials must be available in the environment via one of:
- OIDC role assumption (in GitHub Actions).
- An IAM instance profile (on EC2 / ECS).
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables (local operator use only — rotate after use).

The Python dependencies must be installed:

```bash
pip install -r requirements-dev.txt
```

### Finding the Runtime ID and Alias ID

The CDK stack emits CloudFormation outputs after each deploy. You can retrieve them with:

```bash
aws cloudformation describe-stacks \
    --stack-name AgentStack-Production \
    --query 'Stacks[0].Outputs' \
    --output table
```

The AgentCore runtime ID and alias ID are also stored in SSM Parameter Store under:

```
/ncino/banking-agent/production/agent-runtime-id
/ncino/banking-agent/production/agent-alias-id
```

---

## 3. Incident Response Checklist

### Step 1 — Alarm Fires

The `ncino-banking-agent-production-error-count` CloudWatch alarm publishes to the SNS topic `agentcore-alerts-production`. Subscribers (PagerDuty / email) receive a notification.

Actions:
- [ ] Acknowledge the alert in PagerDuty to prevent escalation while you investigate.
- [ ] Note the exact alarm trigger time and open the CloudWatch Logs Insights console.

### Step 2 — Triage

**Check the logs:**

```bash
aws logs filter-log-events \
    --log-group-name /aws/agentcore/ncino-banking-agent/production \
    --start-time $(date -d '-30 minutes' +%s000) \
    --filter-pattern "ERROR" \
    --output text
```

**Check recent deployments:**

```bash
aws cloudformation describe-stack-events \
    --stack-name AgentStack-Production \
    --query 'StackEvents[?ResourceStatus==`UPDATE_COMPLETE`].[Timestamp,LogicalResourceId]' \
    --output table
```

**Check the error alarm metrics:**

```bash
aws cloudwatch get-metric-statistics \
    --namespace NcinoBankingAgent \
    --metric-name ErrorCount-production \
    --start-time $(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 300 \
    --statistics Sum \
    --output table
```

- [ ] Determine if the errors are transient spikes or sustained.
- [ ] Check whether a deployment happened within 30 minutes of the alarm.
- [ ] Check the Trivy scan report in the GitHub Actions run for the deployed SHA.

### Step 3 — Contain

If errors are caused by a bad deployment:
- [ ] Execute the rollback command in Section 2.
- [ ] Verify the alarm returns to OK state within two evaluation periods (10 minutes).
- [ ] Run the smoke test manually against production (Section 4).

If errors are infrastructure-related (not caused by a deployment):
- [ ] Check the AWS Service Health Dashboard for Bedrock and ECR incidents in `us-east-1`.
- [ ] If an AWS incident is confirmed, post a status update to the team channel and wait.

### Step 4 — Escalation Path

| Severity | Criteria                                          | Escalate To                         | SLA      |
|----------|---------------------------------------------------|-------------------------------------|----------|
| P1       | Production down, all requests failing             | Engineering Manager + AWS Support   | 15 min   |
| P2       | Error rate > 10%, partial degradation             | On-call Platform Engineer           | 30 min   |
| P3       | Error rate elevated but below alarm threshold     | Team Slack channel                  | 2 hours  |

### Step 5 — Post-Incident

- [ ] Write an incident summary in Confluence within 24 hours.
- [ ] Create a GitHub Issue for the root cause with label `post-incident`.
- [ ] Update evaluation thresholds or add regression tests if the incident was caused by a model quality issue.
- [ ] Confirm the CloudWatch alarm returned to OK and SNS sent the OK notification.

---

## 4. Running Smoke Tests Manually

The smoke test script (`scripts/smoke_test.py`) runs two tiers of checks:

1. **Static checks** — verifies the agent package is importable and that core logic (tool functions, system prompt) is correct. These run without AWS credentials.

2. **Live endpoint check** — invokes the live AgentCore runtime with the prompt _"How many days old is someone born on 1990-01-01?"_ and asserts the response is non-empty, contains the word "days", and contains at least one numeric character. Retries up to three times with a five-second delay to handle cold-start latency. This check requires AWS credentials and an agent ID environment variable; it is skipped (with a warning) when neither is set.

### Prerequisites

- Python dependencies installed: `pip install -r requirements-dev.txt`
- AWS credentials available with `bedrock-agentcore:InvokeAgentRuntime` permission.
- The `AGENT_ID_STAGING` or `AGENT_ID_PRODUCTION` environment variable set to the target environment's AgentCore runtime ID (or the generic `AGENT_ID` fallback).

### Staging

```bash
export AGENT_ID_STAGING=<staging-agent-runtime-id>
export AWS_REGION=us-east-1

python scripts/smoke_test.py --environment staging
```

### Production

```bash
export AGENT_ID_PRODUCTION=<production-agent-runtime-id>
export AWS_REGION=us-east-1

python scripts/smoke_test.py --environment production
```

The script exits `0` when all checks pass (or when the live check is skipped due to a missing agent ID) and `1` on any failure, printing a clear PASS/FAIL/SKIP status for each check.

---

## 5. Environment Variable Reference

### Pipeline Variables (GitHub Actions `env:`)

| Variable          | Value                  | Description                                      |
|-------------------|------------------------|--------------------------------------------------|
| `AWS_REGION`      | `us-east-1`            | AWS region for all deployments                   |
| `ECR_REPOSITORY`  | `ncino-banking-agent`  | Base ECR repository name (environment appended)  |
| `PYTHON_VERSION`  | `3.12`                 | Python version used in all CI jobs               |

### GitHub Actions Secrets

| Secret                  | Required By          | Description                                          |
|-------------------------|----------------------|------------------------------------------------------|
| `AWS_STAGING_ROLE_ARN`  | `deploy-staging`     | OIDC role ARN assumed for staging deployments        |
| `AWS_PROD_ROLE_ARN`     | `deploy-production`  | OIDC role ARN assumed for production deployments     |
| `ECR_REGISTRY`          | `build-and-scan`, `deploy-staging`, `deploy-production` | ECR registry hostname (`<account>.dkr.ecr.<region>.amazonaws.com`) |

### Application Runtime Variables

| Variable      | Default         | Description                                                          |
|---------------|-----------------|----------------------------------------------------------------------|
| `MODEL_ARN`   | _(required)_    | Full Bedrock foundation model ARN passed to `BedrockModel(model_id=)` |
| `AWS_REGION`  | `us-east-1`     | AWS region used by boto3 clients inside the container                |

### CDK Deployment Variables

| Variable              | Default    | Description                                                             |
|-----------------------|------------|-------------------------------------------------------------------------|
| `IMAGE_TAG`           | `latest`   | Immutable git SHA image tag injected by the pipeline into CDK stacks    |
| `MODEL_ARN`           | _(required in deploy)_ | Bedrock model ARN scoped into the `BedrockInvoke` IAM policy  |
| `CDK_DEFAULT_ACCOUNT` | _(from AWS credentials)_ | AWS account ID for stack deployment                         |
| `CDK_DEFAULT_REGION`  | `us-east-1` | AWS region for stack deployment                                        |

### Smoke Test Variables

| Variable                | Description                                                       |
|-------------------------|-------------------------------------------------------------------|
| `AGENT_ID`              | Fallback AgentCore runtime ID (used if environment-specific var is not set) |
| `AGENT_ID_STAGING`      | AgentCore runtime ID for the staging environment                  |
| `AGENT_ID_PRODUCTION`   | AgentCore runtime ID for the production environment               |

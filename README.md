# Age Calculator Agent

A Strands Agents SDK application that calculates a user's age in days using AWS Bedrock. The agent accepts a birthdate, retrieves today's date via a tool call, and computes the difference.

## Requirements

- Python 3.11+
- AWS account with Bedrock access
- An [application inference profile](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles.html) ARN

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and set your model ARN:

```bash
cp .env.example .env
# Edit .env and set MODEL_ARN
```

**.env**
```
MODEL_ARN=arn:aws:bedrock:us-east-1:ACCOUNT_ID:application-inference-profile/PROFILE_ID
```

Run the agent:

```bash
python main.py
```

## Running tests

```bash
# Full suite (unit + integration + evaluation), requires no AWS credentials
pytest

# Unit tests only
pytest tests/unit

# Evaluation tests only (structural dataset checks, no live inference)
pytest tests/evaluation -m evaluation --no-cov
```

Coverage is enforced at 90% minimum. The current suite has 122 tests at 98% coverage.

## Linting and type checking

```bash
ruff check age_calculator/
mypy age_calculator/ --strict
```

## Docker

**Build:**
```bash
docker build --target final -t age-calculator-agent:local .
```

**Run:**
```bash
docker run -e MODEL_ARN=arn:aws:bedrock:us-east-1:ACCOUNT_ID:application-inference-profile/PROFILE_ID \
  age-calculator-agent:local
```

The image runs as a non-root user (`agentuser:1000`) and includes a health check that validates the package is importable every 30 seconds.

## CI/CD pipeline

The GitHub Actions workflow (`.github/workflows/agent-deploy.yml`) runs the following stages on every push to `main` or `develop`:

| Stage | What it does |
|-------|-------------|
| **Validate** | `ruff` lint + `mypy --strict` type check |
| **Unit Test** | `pytest tests/unit` with 90% coverage gate |
| **Evaluate** | `pytest tests/evaluation` + threshold checks via `scripts/check_threshold.py` |
| **Build and Scan** | Docker build + Trivy scan (fails on HIGH/CRITICAL CVEs) |
| **Deploy Staging** | Push to ECR, smoke test via `scripts/smoke_test.py` (requires manual approval) |
| **Deploy Production** | Same as staging, `main` branch only (requires manual approval) |

### Required GitHub secrets

| Secret | Description |
|--------|-------------|
| `AWS_STAGING_ROLE_ARN` | IAM role ARN for staging deployments (OIDC) |
| `AWS_PROD_ROLE_ARN` | IAM role ARN for production deployments (OIDC) |
| `ECR_REGISTRY` | ECR registry URL (e.g. `123456789.dkr.ecr.us-east-1.amazonaws.com`) |

### Required AWS IAM permissions

The deployment role needs:
```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:PutImage",
    "ecr:InitiateLayerUpload",
    "ecr:UploadLayerPart",
    "ecr:CompleteLayerUpload"
  ],
  "Resource": "arn:aws:ecr:us-east-1:ACCOUNT_ID:repository/age-calculator-agent"
}
```

The runtime role (used by the agent container) needs:
```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": "arn:aws:bedrock:us-east-1:ACCOUNT_ID:application-inference-profile/PROFILE_ID"
}
```

## Project structure

```
age_calculator/       # Agent package
  agent.py            # Agent factory and system prompt
  config.py           # Pydantic settings (MODEL_ARN from environment)
  tools.py            # @tool functions: get_current_date, calculate_days_between
  __init__.py         # Public API: create_agent
main.py               # CLI entry point
scripts/
  check_threshold.py  # CI threshold gate (reads pytest JUnit XML)
  smoke_test.py       # Post-deploy smoke checks (no live AWS calls)
tests/
  unit/               # Fast tests, no AWS credentials required
  integration/        # Agent wiring tests with mocked Bedrock
  evaluation/         # Ground truth dataset (43 cases) + structural checks
Dockerfile            # Multi-stage build
```

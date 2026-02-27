"""Shared pytest fixtures for the strands-agents-qa test suite.

Fixtures defined here are available to all test modules (unit, integration,
evaluation) without any import.

No AWS credentials are required — the ``agent_runner`` fixture patches
``BedrockModel`` before any SDK initialisation can attempt a network call.
"""

import os

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure MODEL_ARN is set before any test module is collected.
# The module-level ``settings = Settings()`` call in config.py runs at
# collection time; without this sentinel value pydantic-settings raises a
# ValidationError and the entire collection fails.
# ---------------------------------------------------------------------------
os.environ.setdefault("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/test-model")


# ---------------------------------------------------------------------------
# Model fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bedrock_model() -> MagicMock:
    """A MagicMock standing in for ``BedrockModel`` — no AWS credentials needed.

    The mock's ``invoke`` return value mimics the minimal Bedrock response
    shape so that any code path that calls ``model.invoke()`` directly receives
    a structurally valid dict.
    """
    model = MagicMock()
    model.invoke.return_value = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Mocked response"}],
    }
    return model


# ---------------------------------------------------------------------------
# Agent fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent_runner(mock_bedrock_model: MagicMock):
    """Fully constructed ``strands.Agent`` with ``BedrockModel`` patched out.

    Use this fixture in integration tests and evaluation tests to obtain a
    real agent whose tool registry, system prompt, and message list are live,
    but whose underlying model never makes a Bedrock API call.
    """
    with patch("age_calculator.agent.BedrockModel", return_value=mock_bedrock_model):
        from age_calculator import create_agent
        return create_agent()


# ---------------------------------------------------------------------------
# Date fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def known_start_date() -> str:
    """A well-known start date used across multiple test cases."""
    return "1990-01-01"


@pytest.fixture
def known_end_date() -> str:
    """A well-known end date that forms a 3652-day span with ``known_start_date``."""
    return "2000-01-01"


@pytest.fixture
def leap_year_date() -> str:
    """A valid leap-day date (1996 is a leap year)."""
    return "1996-02-29"


@pytest.fixture
def non_leap_year_date() -> str:
    """A date in a non-leap year used for boundary checks."""
    return "2023-02-28"

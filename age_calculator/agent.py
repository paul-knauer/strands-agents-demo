"""Agent factory for the age calculator.

Call ``create_agent()`` to obtain a configured ``strands.Agent`` instance.
The factory pattern ensures that no Bedrock API calls or SDK initialisation
happen at import time — construction is deferred until the caller explicitly
requests an agent.
"""

import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from age_calculator.config import settings
from age_calculator.tools import calculate_days_between, get_current_date

logger: logging.Logger = logging.getLogger(__name__)

SYSTEM_PROMPT: str = """You are a helpful assistant that calculates a user's age in days.
When the user provides their birthdate, use the get_current_date tool to find today's date,
then use the calculate_days_between tool to compute the number of days between their birthdate
and today. Present the result clearly."""


def create_agent() -> Agent:
    """Create and return a configured age-calculator Strands agent.

    The agent is wired with a ``BedrockModel`` using the ``MODEL_ARN``
    resolved from the environment (see ``age_calculator.config``), and
    is equipped with the ``get_current_date`` and ``calculate_days_between``
    tools.

    Returns:
        A fully initialised ``strands.Agent`` ready to accept user input.
    """
    logger.info("Creating BedrockModel with model_id=%s", settings.model_arn)
    model = BedrockModel(model_id=settings.model_arn)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[get_current_date, calculate_days_between],
    )

    logger.info("Agent created successfully")
    return agent

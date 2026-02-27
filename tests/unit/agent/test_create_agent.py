"""Unit tests for age_calculator.agent.create_agent."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from strands import Agent


@pytest.mark.unit
class TestCreateAgent:
    def test_returns_agent_instance(self, agent_runner):
        assert isinstance(agent_runner, Agent)

    def test_agent_has_get_current_date_tool(self, agent_runner):
        assert "get_current_date" in agent_runner.tool_names

    def test_agent_has_calculate_days_between_tool(self, agent_runner):
        assert "calculate_days_between" in agent_runner.tool_names

    def test_agent_has_exactly_two_tools(self, agent_runner):
        assert len(agent_runner.tool_names) == 2

    def test_bedrock_model_constructed_with_model_arn(self, monkeypatch):
        monkeypatch.setenv("MODEL_ARN", "arn:aws:bedrock:us-east-1::foundation-model/sentinel")

        with patch("age_calculator.agent.BedrockModel") as mock_cls:
            mock_cls.return_value = MagicMock()
            # Reload config and agent so they pick up the new env var value
            import importlib

            import age_calculator.agent as agent_module
            import age_calculator.config as cfg_module
            importlib.reload(cfg_module)
            # Rebind the settings object the agent module uses after reload
            agent_module.settings = cfg_module.Settings()
            agent_module.create_agent()
            mock_cls.assert_called_once_with(model_id="arn:aws:bedrock:us-east-1::foundation-model/sentinel")

    def test_system_prompt_is_non_empty(self):
        from age_calculator.agent import SYSTEM_PROMPT
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 0

    def test_system_prompt_mentions_get_current_date(self):
        from age_calculator.agent import SYSTEM_PROMPT
        assert "get_current_date" in SYSTEM_PROMPT

    def test_system_prompt_mentions_calculate_days_between(self):
        from age_calculator.agent import SYSTEM_PROMPT
        assert "calculate_days_between" in SYSTEM_PROMPT


@pytest.mark.unit
class TestAgentModuleConstants:
    """Unit-level checks on module-level constants and infrastructure in agent.py."""

    def test_system_prompt_describes_days_calculation(self):
        """SYSTEM_PROMPT must orient the model toward computing age in days."""
        from age_calculator.agent import SYSTEM_PROMPT
        assert "days" in SYSTEM_PROMPT.lower()

    def test_system_prompt_describes_birthdate_workflow(self):
        """SYSTEM_PROMPT must instruct the model on the two-step tool workflow."""
        from age_calculator.agent import SYSTEM_PROMPT
        assert "birthdate" in SYSTEM_PROMPT.lower()

    def test_logger_is_named_after_module(self):
        """Logger must use the module's __name__ so log filters work in production."""
        import age_calculator.agent as agent_module
        assert agent_module.logger.name == "age_calculator.agent"

    def test_logger_is_a_logger_instance(self):
        import age_calculator.agent as agent_module
        assert isinstance(agent_module.logger, logging.Logger)

    def test_create_agent_has_docstring(self):
        """create_agent() is a public factory function — it must have a docstring."""
        from age_calculator.agent import create_agent
        assert create_agent.__doc__ is not None
        assert len(create_agent.__doc__.strip()) > 20

    def test_create_agent_return_annotation_is_agent(self):
        """Return type annotation must be present and reference Agent."""
        from age_calculator.agent import create_agent
        hints = create_agent.__annotations__
        assert "return" in hints, "create_agent must declare a return type annotation."

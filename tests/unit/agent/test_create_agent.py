"""Unit tests for age_calculator.agent.create_agent."""

import pytest
from unittest.mock import MagicMock, patch

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
            import age_calculator.config as cfg_module
            importlib.reload(cfg_module)
            import age_calculator.agent as agent_module
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

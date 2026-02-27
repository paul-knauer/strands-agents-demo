"""Unit tests for age_calculator.agent.create_agent and invoke_with_audit."""

import json
import logging
import uuid
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

    def test_audit_logger_is_named_audit(self):
        """audit_logger must use the exact name 'audit' for CloudWatch log routing."""
        import age_calculator.agent as agent_module
        assert agent_module.audit_logger.name == "audit"


@pytest.mark.unit
class TestInvokeWithAudit:
    """Unit tests for invoke_with_audit covering audit record contents and error path."""

    def _make_agent(self, return_value="agent response"):
        mock_agent = MagicMock(return_value=return_value)
        return mock_agent

    def test_happy_path_returns_agent_response(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent("the answer")
        result = invoke_with_audit(agent, "some input")
        assert result == "the answer"

    def test_happy_path_emits_success_status(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["status"] == "success"

    def test_exception_path_emits_error_status(self):
        from age_calculator.agent import invoke_with_audit
        agent = MagicMock(side_effect=RuntimeError("boom"))
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            with pytest.raises(RuntimeError):
                invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["status"] == "error"

    def test_exception_is_reraised(self):
        from age_calculator.agent import invoke_with_audit
        agent = MagicMock(side_effect=ValueError("bad input"))
        with patch("age_calculator.agent.audit_logger"):
            with pytest.raises(ValueError, match="bad input"):
                invoke_with_audit(agent, "some input")

    def test_caller_supplied_session_id_in_audit_record(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        sid = "my-session-42"
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input", session_id=sid)
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["session_id"] == sid

    def test_auto_generated_session_id_is_valid_uuid(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        # Must not raise — validates it is a well-formed UUID
        uuid.UUID(record["session_id"])

    def test_arn_is_masked_in_audit_record(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        import re
        assert not re.search(r":\d{12}:", record["model_id"]), (
            "model_id in audit record must not contain a 12-digit AWS account number"
        )

    def test_latency_is_non_negative(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["response_latency_ms"] >= 0

    def test_audit_record_contains_timestamp(self):
        from age_calculator.agent import invoke_with_audit
        agent = self._make_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert "timestamp" in record
        assert record["timestamp"]

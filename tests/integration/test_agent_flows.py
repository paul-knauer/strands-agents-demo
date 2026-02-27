"""Integration tests for the age-calculator agent end-to-end flows.

These tests construct a real ``strands.Agent`` instance (via ``create_agent``)
but replace the ``BedrockModel`` with a ``MagicMock`` so that no AWS API calls
are made and no credentials are required.

What is tested here (not in unit tests)
---------------------------------------
- ``create_agent`` wires the model, system prompt, and tools together correctly.
- The agent's ``system_prompt`` property reflects the module-level constant.
- The agent's ``messages`` list starts empty for each new instance.
- The agent's ``tool_names`` list exposes exactly the two tools declared in
  ``agent.py`` and nothing else.
- Direct tool invocation via ``agent.tool.<name>()`` routes to the real tool
  implementation (tools are deterministic, no AWS involved).
- Tool docstrings are accessible through the agent's tool registry so that the
  model can read them (a regression guard: if the @tool decorator strips
  docstrings, tool selection quality degrades silently).
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from strands import Agent

from age_calculator.agent import SYSTEM_PROMPT, create_agent
from age_calculator.tools import calculate_days_between, get_current_date

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_agent() -> Agent:
    """Return a create_agent() instance with BedrockModel replaced by a MagicMock."""
    with patch("age_calculator.agent.BedrockModel") as mock_cls:
        mock_cls.return_value = MagicMock()
        return create_agent()


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAgentConstruction:
    """Verify that create_agent() assembles the agent correctly."""

    def test_returns_strands_agent_instance(self, agent_runner: Agent) -> None:
        assert isinstance(agent_runner, Agent)

    def test_agent_messages_empty_on_creation(self, agent_runner: Agent) -> None:
        assert agent_runner.messages == []

    def test_agent_system_prompt_matches_module_constant(self, agent_runner: Agent) -> None:
        assert agent_runner.system_prompt == SYSTEM_PROMPT

    def test_agent_system_prompt_is_non_empty_string(self, agent_runner: Agent) -> None:
        assert isinstance(agent_runner.system_prompt, str)
        assert len(agent_runner.system_prompt.strip()) > 0

    def test_agent_has_exactly_two_tools(self, agent_runner: Agent) -> None:
        assert len(agent_runner.tool_names) == 2

    def test_agent_has_get_current_date_tool(self, agent_runner: Agent) -> None:
        assert "get_current_date" in agent_runner.tool_names

    def test_agent_has_calculate_days_between_tool(self, agent_runner: Agent) -> None:
        assert "calculate_days_between" in agent_runner.tool_names

    def test_two_independent_agent_instances_do_not_share_messages(self) -> None:
        agent_a = _build_agent()
        agent_b = _build_agent()
        # Mutate agent_a's messages to confirm isolation
        agent_a.messages.append({"role": "user", "content": [{"text": "hi"}]})
        assert agent_b.messages == [], (
            "agent_b.messages was modified when agent_a.messages was mutated — "
            "the two instances share a list reference."
        )


# ---------------------------------------------------------------------------
# System prompt content
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSystemPromptContent:
    """The system prompt must contain the information the model needs to behave correctly."""

    def test_system_prompt_references_get_current_date(self) -> None:
        assert "get_current_date" in SYSTEM_PROMPT

    def test_system_prompt_references_calculate_days_between(self) -> None:
        assert "calculate_days_between" in SYSTEM_PROMPT

    def test_system_prompt_mentions_birthdate(self) -> None:
        assert "birthdate" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_days(self) -> None:
        assert "days" in SYSTEM_PROMPT.lower()

    def test_system_prompt_is_at_least_fifty_chars(self) -> None:
        assert len(SYSTEM_PROMPT.strip()) >= 50


# ---------------------------------------------------------------------------
# BedrockModel receives the configured model ARN
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestBedrockModelConfiguration:
    """create_agent() must pass settings.model_arn to BedrockModel."""

    def test_bedrock_model_called_with_model_arn_kwarg(self, monkeypatch) -> None:
        test_arn = "arn:aws:bedrock:us-east-1::foundation-model/integration-test-model"
        monkeypatch.setenv("MODEL_ARN", test_arn)

        import importlib

        import age_calculator.agent as agent_module
        import age_calculator.config as cfg_module
        importlib.reload(cfg_module)
        agent_module.settings = cfg_module.Settings()

        with patch("age_calculator.agent.BedrockModel") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent_module.create_agent()
            mock_cls.assert_called_once_with(model_id=test_arn)

    def test_bedrock_model_not_called_at_import_time(self) -> None:
        """BedrockModel must not be constructed until create_agent() is called."""
        with patch("age_calculator.agent.BedrockModel") as mock_cls:
            # Import alone should not instantiate the model
            import age_calculator.agent  # noqa: F401
            mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Direct tool invocation via agent.tool.<name>()
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDirectToolInvocationThroughAgent:
    """agent.tool.<name>() should route to the real tool implementation."""

    def test_get_current_date_via_agent_tool_returns_iso_string(
        self, agent_runner: Agent
    ) -> None:
        result = agent_runner.tool.get_current_date()
        # The result is wrapped in a ToolResult-style dict by the SDK
        # Extract the text value regardless of wrapping
        text = result if isinstance(result, str) else str(result)
        # Must be parseable as an ISO date
        try:
            parsed = datetime.date.fromisoformat(text.strip())
        except ValueError:
            # The SDK may wrap the result; search for the date substring
            import re
            match = re.search(r"\d{4}-\d{2}-\d{2}", text)
            assert match, f"No ISO date found in tool result: {text!r}"
            parsed = datetime.date.fromisoformat(match.group())
        assert isinstance(parsed, datetime.date)

    def test_calculate_days_between_via_agent_tool_known_span(
        self, agent_runner: Agent
    ) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="1990-01-01", end_date="2000-01-01"
        )
        # Result may be wrapped; extract the numeric value
        text = result if isinstance(result, str) else str(result)
        assert "3652" in text, (
            f"Expected '3652' in tool result for 1990-01-01 to 2000-01-01, got: {text!r}"
        )

    def test_calculate_days_between_via_agent_tool_same_date(
        self, agent_runner: Agent
    ) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="2000-06-15", end_date="2000-06-15"
        )
        text = result if isinstance(result, str) else str(result)
        assert "0" in text, (
            f"Expected '0' in tool result for same-date span, got: {text!r}"
        )


# ---------------------------------------------------------------------------
# Tool docstring accessibility
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestToolDocstringAccessibility:
    """Tool docstrings must survive the @tool decorator and remain readable.

    The Strands SDK feeds the docstring to the model as the tool description.
    If a decorator strips it, the model has no guidance on when to call the
    tool — this is a silent quality regression.
    """

    def test_get_current_date_docstring_is_accessible(self) -> None:
        assert get_current_date.__doc__ is not None
        assert len(get_current_date.__doc__.strip()) > 50

    def test_get_current_date_docstring_contains_use_directive(self) -> None:
        doc = get_current_date.__doc__.lower()
        assert any(phrase in doc for phrase in ["use this tool", "when", "invoke"])

    def test_get_current_date_docstring_describes_return_format(self) -> None:
        doc = get_current_date.__doc__
        assert "YYYY-MM-DD" in doc or "yyyy-mm-dd" in doc.lower()

    def test_calculate_days_between_docstring_is_accessible(self) -> None:
        assert calculate_days_between.__doc__ is not None
        assert len(calculate_days_between.__doc__.strip()) > 50

    def test_calculate_days_between_docstring_contains_use_directive(self) -> None:
        doc = calculate_days_between.__doc__.lower()
        assert any(phrase in doc for phrase in ["use this tool", "when", "invoke"])

    def test_calculate_days_between_docstring_documents_start_date(self) -> None:
        assert "start_date" in calculate_days_between.__doc__

    def test_calculate_days_between_docstring_documents_end_date(self) -> None:
        assert "end_date" in calculate_days_between.__doc__

    def test_calculate_days_between_docstring_documents_raises(self) -> None:
        doc = calculate_days_between.__doc__
        assert "Raises" in doc or "raises" in doc.lower() or "ValueError" in doc


# ---------------------------------------------------------------------------
# Package public API
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPackagePublicAPI:
    """The age_calculator package must expose create_agent as its public API."""

    def test_create_agent_importable_from_package(self) -> None:
        from age_calculator import create_agent as ca
        assert callable(ca)

    def test_dunder_all_contains_create_agent(self) -> None:
        import age_calculator
        assert "create_agent" in age_calculator.__all__

    def test_dunder_all_is_a_list(self) -> None:
        import age_calculator
        assert isinstance(age_calculator.__all__, list)

    def test_create_agent_is_callable(self) -> None:
        from age_calculator import create_agent as ca
        assert callable(ca)


# ---------------------------------------------------------------------------
# invoke_with_audit end-to-end
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestInvokeWithAuditIntegration:
    """invoke_with_audit must emit a structured audit record on both success and failure.

    Uses a plain MagicMock as the agent so the audit wiring can be tested
    without triggering a live Bedrock call or the full Strands event loop.
    """

    def _mock_agent(self, return_value="ok", side_effect=None):
        m = MagicMock()
        if side_effect is not None:
            m.side_effect = side_effect
        else:
            m.return_value = return_value
        return m

    def test_happy_path_returns_agent_response(self) -> None:
        import json
        from age_calculator.agent import invoke_with_audit
        agent = self._mock_agent(return_value="42 days")
        with patch("age_calculator.agent.audit_logger"):
            result = invoke_with_audit(agent, "some input")
        assert result == "42 days"

    def test_happy_path_emits_success_status(self) -> None:
        import json
        from age_calculator.agent import invoke_with_audit
        agent = self._mock_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["status"] == "success"

    def test_exception_path_emits_error_status(self) -> None:
        import json
        from age_calculator.agent import invoke_with_audit
        agent = self._mock_agent(side_effect=RuntimeError("model error"))
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            with pytest.raises(RuntimeError):
                invoke_with_audit(agent, "some input")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["status"] == "error"

    def test_session_id_present_in_audit_record(self) -> None:
        import json
        from age_calculator.agent import invoke_with_audit
        agent = self._mock_agent()
        with patch("age_calculator.agent.audit_logger") as mock_audit:
            invoke_with_audit(agent, "some input", session_id="integ-session-1")
        record = json.loads(mock_audit.info.call_args[0][0])
        assert record["session_id"] == "integ-session-1"


# ---------------------------------------------------------------------------
# Tool validation branches via direct invocation
# ---------------------------------------------------------------------------

def _tool_result_is_error(result) -> bool:
    """Return True when the Strands SDK wraps a tool exception as an error dict."""
    return isinstance(result, dict) and result.get("status") == "error"


@pytest.mark.integration
class TestToolValidationBranchesIntegration:
    """Validation error branches in the tools must fire correctly when called
    through the agent's tool registry.

    The Strands SDK catches tool exceptions and wraps them in a
    ``{'status': 'error', ...}`` dict rather than propagating them, so
    these tests assert on the returned dict instead of expecting a raise.
    """

    def test_non_string_start_date_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date=19900101, end_date="2024-01-01"  # type: ignore[arg-type]
        )
        assert _tool_result_is_error(result)

    def test_non_string_end_date_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="1990-01-01", end_date=None  # type: ignore[arg-type]
        )
        assert _tool_result_is_error(result)

    def test_invalid_start_date_format_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="not-a-date", end_date="2024-01-01"
        )
        assert _tool_result_is_error(result)

    def test_invalid_end_date_format_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="1990-01-01", end_date="not-a-date"
        )
        assert _tool_result_is_error(result)

    def test_start_date_before_1900_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="1899-12-31", end_date="2024-01-01"
        )
        assert _tool_result_is_error(result)

    def test_end_date_before_1900_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="1900-01-01", end_date="1899-06-01"
        )
        assert _tool_result_is_error(result)

    def test_start_after_end_returns_error(self, agent_runner: Agent) -> None:
        result = agent_runner.tool.calculate_days_between(
            start_date="2024-01-02", end_date="2024-01-01"
        )
        assert _tool_result_is_error(result)

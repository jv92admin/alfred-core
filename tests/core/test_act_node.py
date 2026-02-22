"""
Tests for Act node — routing function, circuit breaker logic.

Uses StubDomainConfig (no kitchen dependency).
Tests should_continue_act routing + circuit breaker + key act_node paths.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from alfred.graph.state import (
    AlfredState,
    ThinkOutput,
    ThinkStep,
    ToolCallAction,
    StepCompleteAction,
    RequestSchemaAction,
    RetrieveStepAction,
    AskUserAction,
    BlockedAction,
    FailAction,
    RouterOutput,
    UnderstandOutput,
)
from alfred.graph.nodes.act import should_continue_act, act_node, MAX_TOOL_CALLS_PER_STEP
from alfred.core.modes import ModeContext


# =============================================================================
# Helpers
# =============================================================================


def _make_state(**overrides) -> dict:
    """Build a minimal AlfredState dict for act node tests."""
    base = {
        "user_id": "test-user",
        "conversation_id": None,
        "user_message": "Show me my items",
        "mode_context": ModeContext.default().to_dict(),
        "current_turn": 1,
        "router_output": RouterOutput(agent="main", goal="Show items", complexity="medium"),
        "understand_output": UnderstandOutput(),
        "think_output": ThinkOutput(
            goal="Show items",
            steps=[
                ThinkStep(description="Read items", step_type="read", subdomain="items", group=0),
            ],
            decision="plan_direct",
        ),
        "context": {},
        "current_step_index": 0,
        "step_results": {},
        "step_metadata": {},
        "current_step_tool_results": [],
        "current_batch_manifest": None,
        "id_registry": None,
        "summarize_output": None,
        "current_subdomain": None,
        "schema_requests": 0,
        "pending_action": None,
        "group_results": {},
        "content_archive": {},
        "prev_step_note": None,
        "conversation": {
            "engagement_summary": "",
            "recent_turns": [],
            "history_summary": "",
            "step_summaries": [],
            "content_archive": {},
            "active_entities": {},
            "all_entities": {},
            "pending_clarification": None,
            "turn_summaries": [],
            "reasoning_summary": "",
        },
        "final_response": None,
        "error": None,
    }
    base.update(overrides)
    return base


# =============================================================================
# should_continue_act — routing logic (pure function, no mocks needed)
# =============================================================================


class TestShouldContinueAct:
    """Test the act loop routing function."""

    def test_no_action_returns_reply(self):
        state = _make_state(pending_action=None)
        assert should_continue_act(state) == "reply"

    def test_tool_call_returns_continue(self):
        state = _make_state(
            pending_action=ToolCallAction(
                tool="db_read", params={"table": "items"}
            )
        )
        assert should_continue_act(state) == "continue"

    def test_step_complete_with_more_steps_returns_continue(self):
        """Step completed and current_step_index < len(steps) → continue."""
        think = ThinkOutput(
            goal="Do stuff",
            steps=[
                ThinkStep(description="Step 1", step_type="read", subdomain="items"),
                ThinkStep(description="Step 2", step_type="write", subdomain="items"),
            ],
            decision="plan_direct",
        )
        state = _make_state(
            think_output=think,
            current_step_index=1,
            pending_action=StepCompleteAction(result_summary="Done step 0"),
        )
        assert should_continue_act(state) == "continue"

    def test_step_complete_all_done_returns_reply(self):
        """All steps completed → reply."""
        think = ThinkOutput(
            goal="Do stuff",
            steps=[
                ThinkStep(description="Step 1", step_type="read", subdomain="items"),
            ],
            decision="plan_direct",
        )
        state = _make_state(
            think_output=think,
            current_step_index=1,
            pending_action=StepCompleteAction(result_summary="All done"),
        )
        assert should_continue_act(state) == "reply"

    def test_request_schema_returns_continue(self):
        state = _make_state(
            pending_action=RequestSchemaAction(subdomain="items")
        )
        assert should_continue_act(state) == "continue"

    def test_retrieve_step_returns_continue(self):
        state = _make_state(
            pending_action=RetrieveStepAction(step_index=0)
        )
        assert should_continue_act(state) == "continue"

    def test_ask_user_returns_ask_user(self):
        state = _make_state(
            pending_action=AskUserAction(
                question="Which item?", context="Multiple matches"
            )
        )
        assert should_continue_act(state) == "ask_user"

    def test_blocked_returns_reply(self):
        state = _make_state(
            pending_action=BlockedAction(
                reason_code="TOOL_FAILURE",
                details="DB error",
                suggested_next="fail",
            )
        )
        assert should_continue_act(state) == "reply"

    def test_fail_returns_fail(self):
        state = _make_state(
            pending_action=FailAction(
                reason="Unrecoverable", user_message="Sorry, something went wrong."
            )
        )
        assert should_continue_act(state) == "fail"


# =============================================================================
# Circuit breaker — early returns, no LLM call needed
# =============================================================================


class TestActNodeCircuitBreaker:
    """Test circuit breaker / safety limits in act_node."""

    async def test_max_tool_calls_forces_completion(self):
        """After MAX_TOOL_CALLS_PER_STEP tool calls, act forces step completion."""
        tool_results = [
            ("db_read", "items", [{"id": f"item_{i}"}])
            for i in range(MAX_TOOL_CALLS_PER_STEP)
        ]
        state = _make_state(current_step_tool_results=tool_results)

        # Circuit breaker fires before any LLM/domain calls — no mocks needed
        result = await act_node(state)

        assert result.get("current_step_index") == 1
        assert isinstance(result.get("pending_action"), StepCompleteAction)
        assert result.get("current_step_tool_results") == []

    async def test_duplicate_empty_reads_forces_completion(self):
        """Two consecutive empty reads on same table forces step completion."""
        tool_results = [
            ("db_read", "items", []),
            ("db_read", "items", []),
        ]
        state = _make_state(current_step_tool_results=tool_results)

        result = await act_node(state)

        assert result.get("current_step_index") == 1
        assert isinstance(result.get("pending_action"), StepCompleteAction)

    async def test_no_think_output_returns_fail(self):
        """Missing think_output returns FailAction."""
        state = _make_state(think_output=None)

        result = await act_node(state)

        assert isinstance(result.get("pending_action"), FailAction)

    async def test_all_steps_done_returns_none_action(self):
        """When current_step_index >= len(steps), returns pending_action=None."""
        state = _make_state(current_step_index=1)  # 1 step, index=1 → done

        result = await act_node(state)

        assert result.get("pending_action") is None


# =============================================================================
# Act node — tool dispatch (requires LLM mock)
# =============================================================================


class TestActNodeToolDispatch:
    """Test act_node CRUD dispatch and step completion via mocked LLM."""

    def _mock_decision(self, **overrides):
        """Build an ActDecision-like mock."""
        defaults = {
            "action": "tool_call",
            "tool": "db_read",
            "params": {"table": "items", "filters": []},
            "result_summary": None,
            "data": None,
            "note_for_next_step": None,
            "artifacts": None,
            "batch_progress": None,
            "subdomain": None,
            "step_index": None,
            "question": None,
            "context": None,
            "reason": None,
            "user_message": None,
            "reason_code": None,
            "details": None,
            "suggested_next": None,
            "attempted_context": None,
            "archive_key": None,
        }
        defaults.update(overrides)
        mock = MagicMock(**defaults)
        for k, v in defaults.items():
            setattr(mock, k, v)
        return mock

    async def test_tool_call_executes_crud(self):
        """When LLM returns tool_call, execute_crud is called."""
        state = _make_state()
        decision = self._mock_decision(action="tool_call", tool="db_read", params={"table": "items", "filters": []})
        mock_crud_result = [{"id": "item_1", "name": "Widget"}]

        with (
            patch("alfred.graph.nodes.act.call_llm", new_callable=AsyncMock, return_value=decision),
            patch("alfred.graph.nodes.act.execute_crud", new_callable=AsyncMock, return_value=mock_crud_result) as mock_exec,
            patch("alfred.graph.nodes.act.get_schema_with_fallback", new_callable=AsyncMock, return_value="CREATE TABLE items (id uuid);"),
            patch("alfred.graph.nodes.act.set_current_node"),
            patch("alfred.graph.nodes.act.format_full_context", return_value=""),
            patch("alfred.graph.nodes.act.build_act_user_prompt", return_value="mock prompt"),
        ):
            result = await act_node(state)

        mock_exec.assert_called_once()
        # execute_crud may use positional or keyword args — check either way
        call_args, call_kwargs = mock_exec.call_args
        tool_name = call_args[0] if call_args else call_kwargs.get("tool")
        assert tool_name == "db_read"
        # Should continue looping (ToolCallAction)
        assert isinstance(result.get("pending_action"), ToolCallAction)

    async def test_step_complete_advances_index(self):
        """When LLM returns step_complete, step index increments."""
        state = _make_state(
            current_step_tool_results=[
                ("db_read", "items", [{"id": "item_1", "name": "Widget"}])
            ],
        )
        decision = self._mock_decision(
            action="step_complete",
            result_summary="Found 1 item",
            note_for_next_step="item_1 is the Widget",
        )

        with (
            patch("alfred.graph.nodes.act.call_llm", new_callable=AsyncMock, return_value=decision),
            patch("alfred.graph.nodes.act.get_schema_with_fallback", new_callable=AsyncMock, return_value=""),
            patch("alfred.graph.nodes.act.set_current_node"),
            patch("alfred.graph.nodes.act.format_full_context", return_value=""),
            patch("alfred.graph.nodes.act.build_act_user_prompt", return_value="mock prompt"),
        ):
            result = await act_node(state)

        assert result.get("current_step_index") == 1
        assert 0 in result.get("step_results", {})
        assert result.get("current_step_tool_results") == []

    async def test_schema_request_blocked_after_limit(self):
        """After 2 schema requests, act returns BlockedAction."""
        state = _make_state(schema_requests=2)
        decision = self._mock_decision(action="request_schema", subdomain="items")

        with (
            patch("alfred.graph.nodes.act.call_llm", new_callable=AsyncMock, return_value=decision),
            patch("alfred.graph.nodes.act.get_schema_with_fallback", new_callable=AsyncMock, return_value=""),
            patch("alfred.graph.nodes.act.set_current_node"),
            patch("alfred.graph.nodes.act.format_full_context", return_value=""),
            patch("alfred.graph.nodes.act.build_act_user_prompt", return_value="mock prompt"),
        ):
            result = await act_node(state)

        action = result.get("pending_action")
        assert isinstance(action, BlockedAction)
        assert action.reason_code == "PLAN_INVALID"

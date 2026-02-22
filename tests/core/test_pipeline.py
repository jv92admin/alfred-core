"""
Tests for pipeline routing and graph structure.

Verifies that the LangGraph workflow routes correctly between nodes
based on node outputs. Tests the routing functions and graph topology.
"""

import pytest
from unittest.mock import MagicMock

from alfred.graph.state import (
    ThinkOutput,
    ThinkStep,
    UnderstandOutput,
)
from alfred.graph.workflow import (
    route_after_understand,
    route_after_think,
    create_alfred_graph,
    compile_alfred_graph,
    _create_default_router_output,
)
from alfred.core.modes import ModeContext


# =============================================================================
# route_after_understand — routing decisions (pure function)
# =============================================================================


class TestRouteAfterUnderstand:
    """Test routing decisions after the Understand node."""

    def test_needs_clarification_routes_to_reply(self):
        state = {
            "understand_output": UnderstandOutput(needs_clarification=True),
            "mode_context": ModeContext.default().to_dict(),
        }
        assert route_after_understand(state) == "reply"

    def test_quick_mode_routes_to_act_quick(self):
        state = {
            "understand_output": UnderstandOutput(
                quick_mode=True,
                quick_mode_confidence=0.9,
                quick_intent="Show items",
                quick_subdomain="items",
            ),
            "mode_context": ModeContext.default().to_dict(),
        }
        assert route_after_understand(state) == "act_quick"

    def test_normal_routes_to_think(self):
        state = {
            "understand_output": UnderstandOutput(),
            "mode_context": ModeContext.default().to_dict(),
        }
        assert route_after_understand(state) == "think"

    def test_no_understand_output_routes_to_think(self):
        """Defensive: missing understand_output falls through to think."""
        state = {
            "understand_output": None,
            "mode_context": ModeContext.default().to_dict(),
        }
        assert route_after_understand(state) == "think"


# =============================================================================
# route_after_think — routing decisions (pure function)
# =============================================================================


class TestRouteAfterThink:
    """Test routing decisions after the Think node."""

    def test_plan_direct_routes_to_act(self):
        state = {
            "think_output": ThinkOutput(
                goal="Do stuff",
                steps=[ThinkStep(description="Read", step_type="read", subdomain="items")],
                decision="plan_direct",
            ),
        }
        assert route_after_think(state) == "act"

    def test_propose_routes_to_reply(self):
        state = {
            "think_output": ThinkOutput(
                goal="Complex thing",
                steps=[],
                decision="propose",
                proposal_message="Here's my plan...",
            ),
        }
        assert route_after_think(state) == "reply"

    def test_clarify_routes_to_reply(self):
        state = {
            "think_output": ThinkOutput(
                goal="Unclear thing",
                steps=[],
                decision="clarify",
                clarification_questions=["What did you mean?"],
            ),
        }
        assert route_after_think(state) == "reply"

    def test_no_think_output_routes_to_reply(self):
        """Defensive: missing think_output falls through to reply."""
        state = {"think_output": None}
        assert route_after_think(state) == "reply"


# =============================================================================
# Graph structure — verify topology
# =============================================================================


class TestGraphStructure:
    """Test that the graph has correct nodes and edges."""

    def test_graph_compiles_without_error(self):
        """Graph compiles successfully with StubDomainConfig."""
        app = compile_alfred_graph()
        assert app is not None

    def test_graph_has_all_nodes(self):
        """Graph contains all required nodes."""
        graph = create_alfred_graph()
        node_names = set(graph.nodes.keys())
        expected = {"understand", "think", "act", "act_quick", "reply", "summarize"}
        assert expected.issubset(node_names)

    def test_graph_entry_point_is_understand(self):
        """Graph starts at the understand node."""
        graph = create_alfred_graph()
        # LangGraph stores entry point as __start__ → first node edge
        edges = graph.edges
        # Check that __start__ connects to understand
        has_start_edge = any(
            (src == "__start__" and dst == "understand")
            for src, dst in edges
        )
        assert has_start_edge


# =============================================================================
# Default router output
# =============================================================================


class TestDefaultRouter:
    """Test the default router output creation."""

    def test_creates_router_output(self):
        result = _create_default_router_output("Show me my items")
        assert result.agent == "main"  # StubDomainConfig.default_agent
        assert result.goal == "Show me my items"
        assert result.complexity == "medium"

    def test_goal_matches_user_message(self):
        result = _create_default_router_output("Add a new widget")
        assert result.goal == "Add a new widget"

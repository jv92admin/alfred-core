"""
Alfred Context API - Unified context building for all nodes.

Three-Layer Context Model:
- Layer 1: Entity Context (what objects exist)
- Layer 2: Conversation History (what was said)
- Layer 3: Reasoning Trace (what LLMs decided)

Each node subscribes to specific slices via build_*_context() functions.
"""

from alfred.context.builders import (
    build_reply_context,
    build_think_context,
    build_understand_context,
)
from alfred.context.conversation import (
    ConversationHistory,
    PendingState,
    format_conversation,
    get_conversation_history,
)
from alfred.context.entity import (
    EntityContext,
    EntitySnapshot,
    format_entity_context,
    get_entity_context,
)
from alfred.context.reasoning import (
    CurationSummary,
    ReasoningTrace,
    StepSummary,
    TurnSummary,
    format_reasoning,
    get_reasoning_trace,
)

# The substrate protocol — the seam-contract import path for external
# consumers (`from alfred.context import DomainContext`). Import isolation
# (no langgraph/instructor anywhere in this package's import chain) is
# enforced by tests/core/test_import_isolation.py.
from alfred.domain.context import DomainContext

# Audience grades (substrate C-6, seam contract §3) — same seam import path.
from alfred.domain.grades import (
    GRADE_EXTERNAL,
    GRADE_REPLY,
    GradeError,
    GradeRegistry,
    GradeRegistryError,
    StripSet,
    UnknownGradeError,
)

__all__ = [
    # Substrate Protocol
    "DomainContext",
    # Audience Grades (C-6)
    "GRADE_EXTERNAL",
    "GRADE_REPLY",
    "GradeError",
    "GradeRegistry",
    "GradeRegistryError",
    "StripSet",
    "UnknownGradeError",
    # Entity Layer
    "EntityContext",
    "EntitySnapshot",
    "get_entity_context",
    "format_entity_context",
    # Conversation Layer
    "ConversationHistory",
    "PendingState",
    "get_conversation_history",
    "format_conversation",
    # Reasoning Layer
    "ReasoningTrace",
    "TurnSummary",
    "StepSummary",
    "CurationSummary",
    "get_reasoning_trace",
    "format_reasoning",
    # Node Builders
    "build_understand_context",
    "build_think_context",
    "build_reply_context",
    # Note: build_act_entity_context() lives in act.py (requires SessionIdRegistry methods)
]

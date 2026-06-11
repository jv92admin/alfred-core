"""
AgentConfig Protocol — the pipeline half of the domain configuration split.

AgentConfig holds everything whose semantics require the LangGraph pipeline
(nodes, steps, turns, modes, agents, conversation memory), LLM behavior
(prompt content, personas, LLM config, prompt logging), or user-facing
conversational rendering. Non-pipeline consumers never depend on this half.

Note: AgentConfig re-declares ``name`` and ``entities`` as abstract members
because several of its default implementations derive from them. In the
composed ``DomainConfig`` (alfred.domain.base) the declarations merge with
DomainContext's via the MRO — implementers define each exactly once.

Single-call prompts and output schemas for non-pipeline modes are deliberately
in NEITHER protocol — they are mode-owned (0610-mode-language.md §8.2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from alfred.domain.context import EntityDefinition


@dataclass
class ToolDefinition:
    """
    A domain-provided tool available during Act steps.

    Domains register custom tools alongside built-in CRUD via
    DomainConfig.get_custom_tools(). Core dispatches tool calls
    by name — the domain owns the handler implementation.

    Attributes:
        name: Tool name the LLM emits in ActDecision.tool (e.g., "run_python")
        description: One-line description for the LLM decision prompt
        params_schema: Human-readable param docs for the LLM prompt
        handler: Async function (params: dict, user_id: str, context: ToolContext) -> Any
    """

    name: str
    description: str
    params_schema: str
    handler: Callable  # async (params: dict, user_id: str, context: ToolContext) -> Any


@dataclass
class ToolContext:
    """
    Context passed to custom tool handlers during execution.

    Provides access to session state without coupling domains to
    core internals. The handler can use this to look up DataFrames
    from prior steps, translate refs, or inspect state.

    Attributes:
        registry: SessionIdRegistry instance (ref ↔ UUID translation)
        step_results: Results from prior steps in this turn
        current_step_results: Tool results from current step so far
        state: Full AlfredState dict (read-only by convention)
    """

    registry: Any  # SessionIdRegistry
    step_results: list
    current_step_results: list
    state: dict  # AlfredState — mutable dict, treat as read-only


class AgentConfig(ABC):
    """
    The pipeline half of a domain configuration: personas, prompts, modes,
    agents, conversation behavior, and handoff contracts.

    The substrate half lives in DomainContext (alfred.domain.context); the
    composed DomainConfig (alfred.domain.base) is what full pipeline domains
    implement.
    """

    # =========================================================================
    # Structural Members Re-declared (defaults below derive from them)
    # =========================================================================

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain name (e.g., 'kitchen', 'fpl')."""
        ...

    @property
    @abstractmethod
    def entities(self) -> dict[str, EntityDefinition]:
        """
        Entity definitions keyed by table name.

        Returns:
            Dict mapping table name to EntityDefinition
        """
        ...

    # =========================================================================
    # Prompt/Persona Providers
    # =========================================================================

    @abstractmethod
    def get_persona(self, subdomain: str, step_type: str) -> str:
        """
        Get the persona/system prompt for a subdomain and step type.

        Args:
            subdomain: The subdomain (e.g., "recipes", "inventory")
            step_type: The step type (e.g., "read", "write", "analyze")

        Returns:
            Persona text for the LLM
        """
        ...

    @abstractmethod
    def get_examples(
        self,
        subdomain: str,
        step_type: str,
        step_description: str = "",
        prev_subdomain: str | None = None,
    ) -> str:
        """
        Get example interactions for a subdomain and step type.

        Args:
            subdomain: The subdomain (e.g., "recipes", "inventory")
            step_type: The step type (e.g., "read", "write", "analyze")
            step_description: Description of the current step (for contextual matching)
            prev_subdomain: Previous step's subdomain (for cross-domain patterns)

        Returns:
            Example text for the LLM
        """
        ...

    def get_act_subdomain_header(self, subdomain: str, step_type: str) -> str:
        """
        Get the subdomain header for Act prompt context.

        Combines subdomain intro, persona, and scope into a single header block
        used at the top of Act prompts.

        Args:
            subdomain: The subdomain
            step_type: The step type

        Returns:
            Combined header markdown, or empty string
        """
        return ""

    @abstractmethod
    def get_empty_response(self, subdomain: str) -> str:
        """
        Get the empty response message for a subdomain.

        Used when a read returns no results.

        Args:
            subdomain: The subdomain

        Returns:
            Human-friendly "no results" message
        """
        ...

    # =========================================================================
    # Entity Context Configuration
    # =========================================================================

    def get_entity_recency_window(self) -> int:
        """
        Number of turns to consider entities as 'recent' (automatically active).

        Entities referenced within this many turns are included in Think/Act
        context without needing explicit Understand retention.

        Override in domains with high-volume data tables (e.g., return 1).

        Returns:
            Number of turns. Default: 2.
        """
        return 2

    # =========================================================================
    # Act Prompt Configuration
    # =========================================================================

    def get_tool_enabled_step_types(self) -> set[str]:
        """
        Step types that have tool access in Act prompts.

        Controls WHEN tools are available:
        - read/write steps: CRUD tools (db_read, db_create, etc.) + custom tools
        - analyze steps: db_analyze (analytical queries) + calculate (safe arithmetic) + custom tools
        - generate steps: custom tools only

        Default: {"read", "write", "analyze"} — analyze steps get db_analyze
        for aggregate queries (count, sum, avg, min, max + GROUP BY) and
        calculate for safe arithmetic evaluation.

        Override to exclude "analyze" if your domain doesn't need analytical
        queries, or include "generate" for custom generation tools.

        Returns:
            Set of step type strings. Valid values: "read", "write", "analyze", "generate".
        """
        return {"read", "write", "analyze"}

    def get_custom_tools(self) -> dict[str, ToolDefinition]:
        """
        Domain-specific tools available during Act steps.

        Tools registered here are injected into Act prompts when tools are
        enabled for the step type (via get_tool_enabled_step_types()) and
        dispatched by act_node's tool_call handler.

        Custom tools appear independently from CRUD:
        - read/write steps: CRUD tools + custom tools
        - analyze/generate steps (if tool-enabled): custom tools only

        Each tool's handler receives (params, user_id, ToolContext) and returns
        a JSON-serializable result dict. For soft failures, return an error dict
        (LLM retries within MAX_TOOL_CALLS_PER_STEP=3). For hard failures,
        raise an exception (→ BlockedAction, step terminates).

        Returns:
            Dict mapping tool name to ToolDefinition. Default: {} (no custom tools).
        """
        return {}

    def get_crud_reference(self) -> str:
        """
        Get CRUD tools reference content for read/write Act steps.

        Returns markdown documenting db_read, db_create, db_update, db_delete
        tools and their param syntax. Injected into Act prompts for read/write
        steps only (not analyze/generate).

        Override to replace core's crud.md with domain-specific tool docs,
        or return custom content if your CRUD layer has different tools.

        Returns:
            Markdown string with CRUD reference, or empty string to use
            core's built-in crud.md template.
        """
        return ""  # Default: use core's crud.md

    def get_act_step_template(self, step_type: str) -> str:
        """
        Get step-type template for Act prompts.

        Returns markdown with step-type-specific mechanics (how to execute,
        output format, quality principles). Called for each step: read, write,
        analyze, generate.

        Override to replace individual step templates without losing base.md,
        entity tagging, CRUD reference, or the decision builder. Only the
        step-type layer is replaced.

        Args:
            step_type: The act step type (read, write, analyze, generate)

        Returns:
            Markdown string with step template, or empty string to use
            core's built-in {step_type}.md template.
        """
        return ""  # Default: use core's template

    # =========================================================================
    # LLM Observability
    # =========================================================================

    def get_prompt_log_adapter(self):
        """
        Return a DB adapter for prompt log storage, or None to disable.

        Only domains with a prompt_logs table should return an adapter.
        Core's prompt logger uses this for optional DB-based logging.

        Returns:
            A Supabase client (or compatible), or None to skip DB logging.
        """
        return None

    @abstractmethod
    def get_subdomain_examples(self) -> dict[str, list[str]]:
        """
        Get example queries per subdomain for Think node guidance.

        Returns:
            Dict mapping subdomain to list of example queries
        """
        ...

    # =========================================================================
    # Pipeline Archive / Conversation Tracking
    # =========================================================================

    def get_archive_key_for_description(self, description: str) -> str | None:
        """
        Infer a semantic archive key from a step description.

        Used for archiving generate/analyze results with meaningful keys.

        Args:
            description: Step description text

        Returns:
            Archive key string, or None for default key
        """
        return None  # Default: no semantic key

    def get_archive_keys_for_subdomain(self, subdomain: str) -> list[str]:
        """
        Get archive keys to clear when saving to a subdomain.

        After a successful write, related archive entries should be cleared
        to prevent stale generated content from persisting.

        Args:
            subdomain: The subdomain being written to

        Returns:
            List of archive keys to clear
        """
        return []  # Default: don't clear any

    def get_bold_skip_words(self) -> list[str]:
        """
        Words to skip when extracting entity names from bold markdown text.

        Bold text in assistant responses often contains entity names
        (e.g., **Chicken Tikka Masala**) but also section headings
        (e.g., **Ingredients**, **Instructions**). This list filters
        out common non-entity headings.

        Returns:
            List of lowercase words/phrases to skip
        """
        return []  # Default: no skip words

    def get_generated_content_markers(self) -> list[str]:
        """
        Markers that indicate assistant responses contain generated content.

        Used to detect when a message contains domain-specific generated
        content (e.g., recipe instructions, workout plans) for summarization.

        Returns:
            List of marker strings to check for (case-insensitive)
        """
        return []  # Default: no markers

    def get_generated_content_label(self) -> str:
        """
        Label for generated content in conversation summaries.

        Returns:
            Label string (e.g., "recipe", "workout plan")
        """
        return "content"

    def get_relevant_entity_types(self) -> set[str]:
        """
        Entity types considered relevant for conversation context display.

        Filters out low-level entity types (e.g., ingredients, sub-items)
        that would clutter the context.

        Returns:
            Set of entity type names to show in context
        """
        # Default: all entity types with complexity set
        return {e.type_name for e in self.entities.values() if e.complexity}

    def get_tracked_entity_types(self) -> set[str]:
        """
        Get entity types that should be tracked across orchestration steps.

        Returns both table names and type names for flexible matching.

        Returns:
            Set of entity type identifiers
        """
        # Default: derive from entities with complexity hints
        tracked = set()
        for entity in self.entities.values():
            if entity.complexity:
                tracked.add(entity.table)
                tracked.add(entity.type_name)
        return tracked

    def get_item_tracking_keys(self) -> list[str]:
        """
        Get dict keys to check when tracking item names from results.

        These are top-level keys in result dicts that contain lists of items
        with 'name' fields (e.g., "recipes", "tasks").

        Returns:
            List of key names to check
        """
        # Default: derive from entity table names
        return list(self.entities.keys())

    # =========================================================================
    # Reply Rendering (user-bound)
    # =========================================================================

    @abstractmethod
    def get_subdomain_formatters(self) -> dict[str, Callable]:
        """
        Get domain-specific reply formatters per subdomain.

        These formatters transform raw data into user-friendly output.

        Returns:
            Dict mapping subdomain to formatter function
        """
        ...

    def get_system_prompt(self) -> str:
        """
        Get the domain-specific system prompt.

        The system prompt defines the assistant's identity and behavior.

        Returns:
            System prompt string
        """
        return f"You are a helpful {self.name} assistant."

    def get_quick_write_confirmation(self, subdomain: str, count: int, action: str) -> str | None:
        """
        Get a confirmation message for quick-mode write operations.

        E.g., "Added 3 items to your shopping list." or "Added 2 items to your pantry."

        Args:
            subdomain: The subdomain written to
            count: Number of items affected
            action: The action performed (e.g., "add", "delete")

        Returns:
            Confirmation string, or None for generic handling
        """
        return None  # Default: no domain-specific confirmations

    def get_priority_fields(self) -> list[str]:
        """
        Get human-readable fields to prioritize in record display.

        These are the most useful fields to show when formatting records
        for user-facing replies.

        Returns:
            Ordered list of field names
        """
        return ["name", "title", "date", "description", "notes", "category"]

    def format_records_for_reply(
        self, records: list[dict], table_type: str | None, indent: int = 2
    ) -> str | None:
        """
        Format records for user-facing reply display.

        Domain-specific formatting for tables that need special treatment
        (e.g., preferences as key-value, recipes with full instructions).

        Args:
            records: List of record dicts
            table_type: Detected table type (from infer_table_from_record)
            indent: Indentation spaces

        Returns:
            Formatted string, or None to use generic formatting
        """
        return None  # Default: use generic formatting

    # =========================================================================
    # Mode/Agent Registration
    # =========================================================================

    @property
    @abstractmethod
    def bypass_modes(self) -> dict[str, type]:
        """
        Get domain-specific graph-bypass mode handlers.

        These are modes that skip the LangGraph pipeline entirely
        (e.g., cook mode, brainstorm mode).

        Returns:
            Dict mapping mode name to handler class
        """
        ...

    @property
    @abstractmethod
    def default_agent(self) -> str:
        """
        Get the default agent name for single-agent mode.

        Used by _create_default_router_output() in workflow.

        Returns:
            Agent name (e.g., "main", "fpl_main")
        """
        ...

    @property
    def agents(self) -> list:
        """
        Get the list of available agents for this domain.

        Phase 2.5: Returns AgentProtocol instances for multi-agent support.
        Default implementation returns empty list (single-agent mode).

        Returns:
            List of AgentProtocol instances
        """
        return []  # Default: no agents registered (uses bypass_modes)

    @property
    def agent_router(self):
        """
        Get the agent router for multi-agent mode.

        Phase 2.5: Returns AgentRouter instance or None for single-agent.
        Default implementation returns None (single-agent mode).

        Returns:
            AgentRouter instance or None
        """
        return None  # Default: single-agent mode

    def get_mode_llm_config(self) -> dict[str, dict[str, Any]]:
        """
        Get LLM config overrides for domain-specific bypass modes.

        Keys are mode/node names (e.g., "cook", "brainstorm").
        Values are dicts with optional "verbosity" and "temperature" keys.

        Returns:
            Dict mapping mode name to LLM config overrides
        """
        return {}  # Default: no bypass mode LLM configs

    def get_reply_prompt_content(self) -> str:
        """
        Get domain-specific reply instructions for the Reply node.

        Returns the full reply template with domain-specific examples
        in <identity>, <subdomains>, and <principles> sections.
        When provided, this replaces the core reply.md template entirely
        (but NOT the system prompt header from get_system_prompt()).

        Returns:
            Markdown string with the complete Reply instructions,
            or empty string to fall back to core template + injection.
        """
        return ""  # Default: fall back to core template + injection

    def get_act_prompt_content(self, step_type: str) -> str:
        """
        Get domain-specific full system prompt for the Act node.

        Returns the complete Act system prompt for the given step type,
        including base layer, CRUD tools reference (for read/write),
        step-type mechanics, and domain-specific examples.

        When provided, this replaces the core template assembly entirely.

        Args:
            step_type: The act step type (read, write, analyze, generate)

        Returns:
            Full system prompt string, or empty string to fall back
            to core template assembly + injection.
        """
        return ""  # Default: fall back to core template assembly

    def get_act_prompt_injection(self, step_type: str) -> str:
        """
        Get domain-specific guidance to append to Act node prompts.

        Called for each step type (read, write, analyze, generate).
        Returns markdown text appended after the core Act prompt layers.

        Args:
            step_type: The act step type (read, write, analyze, generate)

        Returns:
            Markdown string with domain-specific examples and guidance,
            or empty string for no injection.
        """
        return ""  # Default: no domain-specific Act guidance

    def get_think_prompt_content(self) -> str:
        """
        Get domain-specific system prompt for the Think node.

        Returns the full system prompt with domain-specific examples,
        conversation management patterns, output contract examples,
        and all entity-specific guidance. When provided, this replaces
        the core think.md template AND the injection variables entirely.

        Returns:
            Markdown string with the complete Think system prompt,
            or empty string to fall back to core template + injection.
        """
        return ""  # Default: fall back to core template + injection

    def get_understand_prompt_content(self) -> str:
        """
        Get domain-specific content for the Understand node prompt.

        Returns the full prompt body with domain-specific examples,
        reference resolution patterns, quick mode table, curation examples,
        and output contract examples.

        Returns:
            Markdown string with the complete Understand prompt body,
            or empty string to fall back to the core template.
        """
        return ""  # Default: fall back to core template

    def get_understand_system_prompt(self) -> str:
        """
        Get domain-specific system prompt for the Understand node.

        The Understand node's system prompt defines the LLM's role during
        reference resolution, context curation, and quick mode detection.
        Override this to change the role description or disable quick mode
        detection (e.g., always set quick_mode: false for domains that
        need full pipeline processing on every request).

        Returns:
            System prompt string, or empty string to use core default:
            "You are Alfred's MEMORY MANAGER. Your job: (1) resolve entity
            references... (2) curate context... (3) detect quick mode..."
        """
        return ""  # Default: use core's hardcoded system prompt

    def get_filter_schema(self) -> str:
        """
        Get filter operator documentation for Act prompts.

        Returns markdown documenting available filter operators and examples.
        This appears in every Act prompt (via get_subdomain_context) to teach
        the LLM how to construct CRUD filter clauses.

        The default includes all standard operators (=, >, <, >=, <=, in,
        ilike, is_null) plus the semantic search operator (similar) with
        kitchen-oriented examples. Override to replace the examples with
        domain-specific ones, or remove the semantic search section if your
        domain doesn't support it.

        Returns:
            Markdown string with filter syntax documentation.
        """
        return ""  # Default: use core's built-in FILTER_SCHEMA constant

    def get_summarize_system_prompts(self) -> dict[str, str]:
        """
        Get domain-specific system prompts for the Summarize node.

        The Summarize node makes up to 4 LLM calls, each with a system prompt:
        - "response_summary": Summarize what was accomplished in one sentence
        - "turn_compression": Summarize a single conversation exchange
        - "conversation_compression": Merge history into a brief summary
        - "engagement_summary": Update the session theme (1 sentence)

        Override individual keys to replace specific prompts. Keys not present
        in the returned dict fall back to core defaults.

        Returns:
            Dict mapping prompt key to system prompt string.
            Default: {} (use core defaults for all).
        """
        return {}  # Default: use core's built-in system prompts

    def get_think_domain_context(self) -> str:
        """
        Get domain-specific context/philosophy for Think node.

        Replaces the {domain_context} placeholder in think.md.
        Contains the domain's purpose, philosophy, and what it enables.

        Returns:
            Markdown string with domain context.
        """
        return ""  # Default: no domain-specific Think context

    def get_think_planning_guide(self) -> str:
        """
        Get domain-specific planning guide for Think node.

        Replaces the {domain_planning_guide} placeholder in think.md.
        Contains subdomains, linked tables, complex domain descriptions,
        and domain-specific planning patterns.

        Returns:
            Markdown string with planning guide content.
        """
        return ""  # Default: no domain-specific planning guide

    def get_reply_continuity_guidance(self, current_turn: int) -> list[str] | None:
        """
        Get domain-specific continuity guidance for Reply node on turn 2+.

        Called when current_turn > 1 to guide the LLM on how to handle
        multi-turn conversation continuity (e.g., avoiding greetings,
        building on prior discussion).

        Returns:
            List of guidance strings to include in the prompt,
            None to use core defaults, or empty list to suppress entirely.
        """
        return None  # Default: use core continuity guidance

    def get_reply_subdomain_guide(self) -> str:
        """
        Get domain-specific subdomain formatting guide for Reply node.

        Returns markdown describing how to present each subdomain's data
        to the user (e.g., inventory grouped by location, recipes in
        magazine-style format). Injected into reply prompt.

        Returns:
            Markdown string with subdomain presentation rules.
        """
        return ""  # Default: no domain-specific reply formatting

    def get_router_prompt_injection(self) -> str:
        """
        Get domain-specific content for Router prompt.

        Returns markdown with available agents, their descriptions,
        and routing examples. Injected into router prompt.

        Returns:
            Markdown string with agent definitions and examples.
        """
        return ""  # Default: no domain-specific router content

    def get_handoff_system_prompts(self) -> dict[str, str]:
        """
        Get system prompts for bypass mode handoff summaries.

        Returns:
            Dict mapping mode name to handoff system prompt text
        """
        return {}  # Default: no handoff prompts

    @abstractmethod
    def get_handoff_result_model(self) -> type:
        """
        Get the domain-specific HandoffResult Pydantic model.

        Base has: summary, action, action_detail.
        Domain extends with additional fields (e.g., recipe_content, transfer_plan).

        Returns:
            Pydantic model class for handoff results
        """
        ...

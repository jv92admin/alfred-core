# Domain Injection Map

> Every knob, dial, and toggle a domain implementer can turn — organized by what it affects.

---

## How to Read This Document

Alfred's pipeline runs the same graph for every domain. What changes is **what the domain injects**: prompts, entity definitions, tool handlers, formatting logic, and user-facing behavior. This document maps every injection point by the _kind of effect_ it has.

Three categories:

| Category | What It Controls | Who Notices |
|----------|-----------------|-------------|
| **Reasoning** | How the LLM plans, executes, and decides | The LLM (internal quality) |
| **UI & Output** | What the end user sees and how data is presented | The end user |
| **Execution & Capabilities** | What the system _can do_ — tools, modes, data access | Both |

Each section includes concrete examples using hypothetical domains — a **CRM** (contacts, deals, pipelines), a **Project Management** tool (projects, tasks, sprints), and a **Payments** platform (invoices, subscriptions, payouts) — to show how a real domain would configure each knob.

---

## Core Templates vs. Domain Content

Before diving into the injection points, understand what the core provides out of the box and what it expects you to replace.

### What core templates handle (you inherit this for free)

The core ships 11 prompt templates (~1,635 lines) plus inline prompts in each node. These define **pipeline mechanics** — not domain opinions:

| Template | What It Defines |
|----------|-----------------|
| `understand.md` | Reference resolution logic, entity curation rules, quick-mode detection protocol |
| `think.md` | Step-type taxonomy (read/write/analyze/generate), plan structure, decision types (plan_direct/propose/clarify) |
| `act/base.md` | Execution engine role, one-action-per-response rule, step ownership |
| `act/crud.md` | `db_read`/`db_create`/`db_update`/`db_delete` parameter syntax (incl. aggregate params) |
| `act/read.md` | Filter construction, aggregate functions (count/sum/avg/count_distinct), empty result handling |
| `act/write.md` | FK handling, batch operations, linked record creation |
| `act/analyze.md` | Reasoning patterns over in-context data |
| `act/generate.md` | Artifact structure, `gen_*` ref tagging, quality principles |
| `reply.md` | Editorial principles, phase-appropriate tone, formatting guidelines |
| `summarize.md` | Turn compression rules, engagement summary protocol |
| `router.md` | Agent classification (minimal — single-agent mode) |

These are **domain-agnostic**. A CRM domain, a Payments domain, and a Kitchen domain all inherit the same execution mechanics. You override them when you need different _mechanics_, not different _content_.

### What you must provide (no useful defaults)

These are abstract methods — core cannot function without your implementation:

| What | Why Core Can't Default It |
|------|--------------------------|
| `entities` / `subdomains` | Your data model. Core has no idea what tables you have. |
| `get_db_adapter()` | Your database connection. Core doesn't know your Supabase project. |
| `get_examples()` | Domain-specific few-shot examples. Generic examples would hurt more than help. |
| `get_persona()` | Your assistant's subdomain-specific voice. |
| `get_fallback_schemas()` | Your table schemas. Core can introspect at runtime, but needs fallbacks. |
| `get_field_enums()` / `get_semantic_notes()` | Your field constraints and meanings. |
| `compute_entity_label()` | How to name your entities. Core doesn't know which fields matter. |

### What has safe defaults (override when ready)

These methods return empty strings or sensible defaults. The pipeline works without them, but quality improves when you provide domain-specific content:

| Method | Default Behavior | When to Override |
|--------|-----------------|------------------|
| `get_think_domain_context()` | Empty — Think uses generic planning | When Think makes poor subdomain choices |
| `get_think_planning_guide()` | Empty — Think doesn't know your subdomain relationships | When Think plans wrong step sequences |
| `get_act_prompt_injection()` | Empty — Act uses core templates only | When Act makes domain-specific errors (e.g., wrong filter patterns) |
| `get_act_subdomain_header()` | Empty — no subdomain scoping in prompts | When Act confuses tables across subdomains |
| `get_reply_subdomain_guide()` | Empty — Reply uses generic formatting | When Reply formats data awkwardly for your domain |
| `get_system_prompt()` | `"You are a helpful {name} assistant."` | Immediately — this is your assistant's identity |
| `get_user_profile()` | Empty — no personalization | When you have user preferences to inject |
| `get_crud_middleware()` | `None` — raw CRUD, no hooks | When you need semantic search, auto-includes, or validation |
| `get_custom_tools()` | `{}` — no domain tools | When analyze/generate steps need to call external functions |
| `get_subdomain_formatters()` | `{}` — LLM formats everything | When you want deterministic formatting for quick-mode responses |
| `get_summarize_system_prompts()` | `{}` — uses core defaults (4 keys: `response_summary`, `turn_compression`, `conversation_compression`, `engagement_summary`) | When summary examples don't match your entity types |

### Override progression

A practical path from "it works" to "it works great":

```
Day 1:  Implement abstracts. Use core templates. Pipeline runs.
        ↓
Day 2:  Add get_system_prompt(), get_act_subdomain_header(),
        get_examples(). Quality jumps significantly.
        ↓
Day 3:  Add get_think_planning_guide(), get_reply_subdomain_guide().
        Planning and replies improve.
        ↓
Day 4:  Add get_user_profile(), get_subdomain_guidance().
        Personalization kicks in.
        ↓
Week 2: Add get_crud_middleware() for semantic search / pre-processing.
        Add get_custom_tools() for analyze/generate capabilities.
        ↓
Week 3: Graduate to full prompt replacement (get_think_prompt_content(),
        get_act_prompt_content(), etc.) for fine-grained control.
```

---

## Part 1: Reasoning — How the LLM Thinks

These injections shape how the LLM understands requests, plans steps, and makes decisions. The user never sees these directly, but they determine quality.

### 1.1 Understanding the Request

The Understand node is the **memory manager** — it resolves entity references, curates what stays in context, and detects when a request is simple enough for the fast path.

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_understand_prompt_content()` | `""` (use core template) | Full replacement of the Understand prompt body. Controls reference resolution patterns, quick-mode detection rules, and entity curation examples. |
| `get_understand_system_prompt()` | `""` (use core default) | The role description. Override to change what "memory manager" means in your domain or disable quick-mode entirely. |

**When to override:** When your domain has entity reference patterns the core template doesn't cover well — e.g., a CRM where "that deal" could mean a deal, a pipeline stage, or a contact depending on context.

**Example — CRM domain:**
```python
def get_understand_prompt_content(self) -> str:
    return """
    # Reference Resolution
    - "the deal" / "that opportunity" → most recent deal_* ref
    - "their company" → contact's linked company_* ref
    - "the pipeline" → active pipeline_* ref (usually only one)

    # Quick Mode Table
    | Pattern | Subdomain | Intent |
    |---------|-----------|--------|
    | "show my deals" | deals | List user's active deals |
    | "what's in the pipeline" | pipeline | Show pipeline stages with counts |
    | "contact info for [name]" | contacts | Read contact by name |
    """
```

### 1.2 Planning — The Think Node

Think decomposes requests into step-by-step plans. Each step has a `step_type` (read/write/analyze/generate), a `subdomain`, and a `description`.

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_think_prompt_content()` | `""` (use core template) | **Full replacement** of Think's system prompt. Total control over planning logic. |
| `get_think_domain_context()` | `""` | Fills `{domain_context}` placeholder in `think.md` — domain purpose, philosophy, what it enables. |
| `get_think_planning_guide()` | `""` | Fills `{domain_planning_guide}` placeholder — subdomain list, linked tables, entity-specific planning patterns. |

**Full replacement vs. placeholder injection:**
- New domains: start with `get_think_domain_context()` + `get_think_planning_guide()`. The core template handles planning mechanics — you just provide domain knowledge.
- Mature domains: graduate to `get_think_prompt_content()` when you need full control over phrasing, examples, and step-type guidance.

**Example — Project Management domain using placeholders:**
```python
def get_think_domain_context(self) -> str:
    return """You are planning task execution for a project management assistant.
    Projects contain sprints, sprints contain tasks, tasks have assignees and statuses.
    Always read project context before modifying tasks."""

def get_think_planning_guide(self) -> str:
    return """
    ## Subdomains
    - projects: projects table — top-level containers
    - sprints: sprints table + sprint_tasks — time-boxed work periods
    - tasks: tasks table + task_comments, task_attachments — individual work items
    - team: team_members table — people and roles

    ## Planning Patterns
    - "move task to done" → read(tasks) → write(tasks) [status update]
    - "sprint report" → read(sprints) → read(tasks) → analyze [summarize progress]
    - "plan next sprint" → read(tasks, backlog) → analyze → generate(sprint plan) → propose
    """
```

### 1.3 Per-User Context in Plans

Think also receives dynamic per-user context to make plans personalized.

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_user_profile(user_id)` | `""` | User profile text injected into `<session_context>`. Async. |
| `get_domain_snapshot(user_id)` | `""` | Domain-state snapshot (counts, upcoming items, status). Async. |
| `get_subdomain_guidance(user_id)` | `{}` | Per-subdomain user preferences. `dict[str, str]`. Async. |

These three methods are called in both Think and Act, so the planner and executor share the same user context.

**Example — Payments domain:**
```python
async def get_user_profile(self, user_id: str) -> str:
    return "Business: Acme Corp. Plan: Pro. Currency: USD. Tax region: US-CA."

async def get_domain_snapshot(self, user_id: str) -> str:
    return "12 active subscriptions. 3 invoices overdue. Next payout: Mar 15."

async def get_subdomain_guidance(self, user_id: str) -> dict[str, str]:
    return {
        "invoices": "Always include PO numbers. Net-30 terms unless specified.",
        "subscriptions": "Prefer annual billing. Flag downgrades for review.",
    }
```

### 1.4 Execution — Act Node System Prompts

Act executes each step from Think's plan. Its system prompt varies by step type and is assembled from template layers.

#### The Override Hierarchy

```
1. domain.get_act_prompt_content(step_type)    ← Full replacement (all-or-nothing)
   ↓ returns ""?
2. base.md                                      ← Always included
   + crud.md / domain.get_crud_reference()      ← Read/write only
   + custom tool docs (from get_custom_tools())  ← Any tool-enabled step
   + {step_type}.md / domain.get_act_step_template(step_type)
3. + domain.get_act_prompt_injection(step_type) ← Appended after everything
```

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_act_prompt_content(step_type)` | `""` | Full system prompt for a step type. Bypasses all template layering. |
| `get_crud_reference()` | `""` (use core `crud.md`) | Replaces the CRUD tool documentation section for read/write steps. |
| `get_act_step_template(step_type)` | `""` (use core template) | Replaces the individual `read.md`/`write.md`/`analyze.md`/`generate.md` template without losing `base.md` or CRUD. |
| `get_act_prompt_injection(step_type)` | `""` | Appended after all templates. Domain-specific rules, examples, constraints. |
| `get_filter_schema()` | `""` (use core constant) | Replace filter operator documentation with domain-specific examples. |

**Start here:** `get_act_prompt_injection(step_type)` — append domain rules without replacing anything. Graduate to `get_act_step_template()` or `get_act_prompt_content()` when you need more control.

### 1.5 Execution — Act Node User Prompts (Per-Step Context)

The Act user prompt is assembled from 15 sections. Domain methods feed specific sections:

| Section | Method | Step Types |
|---------|--------|------------|
| 1 — Subdomain header | `get_act_subdomain_header(subdomain, step_type)` | All |
| 2 — Schema | `get_fallback_schemas()` | read, write, generate |
| 3 — User preferences | `get_user_profile()` + `get_subdomain_guidance()` | write |
| 6 — User profile | `get_user_profile()` | analyze, generate |
| 7 — Subdomain guidance | `get_subdomain_guidance()` | analyze, generate |
| 10 — Guidance/examples | `get_examples(subdomain, step_type, desc, prev)` | All |
| 12 — Entity context | `format_entity_for_context(...)` | All |

The other sections (4-STATUS, 5-prev note, 8-task, 9-batch, 11-data, 13-artifacts, 14-conversation, 15-decision) are assembled by core from pipeline state.

**Key abstract methods every domain must implement:**

| Method | What It Provides |
|--------|-----------------|
| `get_persona(subdomain, step_type)` | Persona text for quick-mode Act prompts |
| `get_examples(subdomain, step_type, step_description, prev_subdomain)` | Contextual examples — the most impactful single injection for execution quality |
| `get_fallback_schemas()` | Hardcoded schema strings keyed by **subdomain name** (fallback when DB introspection fails) |

**Example — CRM domain `get_examples()`:**
```python
def get_examples(self, subdomain, step_type, step_description, prev_subdomain):
    if subdomain == "deals" and step_type == "write":
        return """
        ## Examples
        - Moving a deal to "Closed Won":
          `db_update` on deals: set stage="closed_won", closed_date=today
          Then `db_create` on deal_activities: log the win event
        - Creating a deal from a contact:
          `db_create` on deals: set contact_id from the contact's ref
        """
    if subdomain == "contacts" and step_type == "read":
        return """
        ## Examples
        - Search by company: filter contacts where company_id matches
        - "Recent contacts": order_by=last_contacted_at, order_dir=desc, limit=10
        """
    return ""
```

### 1.6 Entity Recency and Context Window

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_entity_recency_window()` | `2` | How many turns an entity stays "recent" in Act's context. Lower = tighter focus. Higher = more memory. |
| `get_tracked_entity_types()` | Entities with `complexity` set | Which entity types appear in entity context at all. |
| `get_relevant_entity_types()` | Entities with `complexity` set | Filter for what's shown in context displays. |
| `get_scope_config()` | `{}` | Cross-subdomain relationship configuration. |

---

## Part 2: UI & Output — What the User Sees

These injections control the final response, how data is formatted, and the assistant's identity.

### 2.1 Assistant Identity

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_system_prompt()` | `"You are a helpful {name} assistant."` | The LLM's identity in Reply. This is who the assistant _is_. |

**Example — Payments domain:**
```python
def get_system_prompt(self) -> str:
    return """You are Alfred, a financial operations assistant.
    You help businesses manage invoices, subscriptions, and payouts.
    Be precise with numbers. Always confirm amounts before executing writes.
    Never round currency values."""
```

### 2.2 Reply Formatting

Reply generates the user-facing response. It has its own override chain:

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_reply_prompt_content()` | `""` (use core `reply.md`) | Full replacement of reply formatting instructions. |
| `get_reply_subdomain_guide()` | `""` | Fills `{domain_subdomain_guide}` in `reply.md`. How to present each subdomain's data. |

**Reply is where "generate" output becomes user-facing.** When the Act pipeline runs a `generate` step (e.g., "draft an invoice"), the generated content flows through Reply, which formats and presents it. But Reply can also do much more — it controls tone, structure, what gets emphasized, and what gets hidden.

**Example — CRM domain reply guide:**
```python
def get_reply_subdomain_guide(self) -> str:
    return """
    ## Deals
    - Always show: deal name, stage, value, expected close date
    - Show pipeline progression as a visual: Discovery → Proposal → Negotiation → ✓ Closed Won
    - For deal lists: sort by value descending, group by stage

    ## Contacts
    - Lead with name and company
    - Show last interaction date and channel
    - Never show internal scores or lead grades to the user
    """
```

### 2.3 Quick-Mode Response Formatters

For simple requests (quick mode), Reply can skip the LLM entirely and use deterministic formatters:

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_subdomain_formatters()` | `{}` | `dict[str, Callable]` — per-subdomain functions that format list results directly. No LLM call. |
| `get_empty_response(subdomain)` | *(abstract)* | What to say when a read returns zero results. |
| `get_quick_write_confirmation(subdomain, count, action)` | `None` | Confirmation message for quick writes. |

**Example — Project Management domain:**
```python
def get_subdomain_formatters(self) -> dict:
    return {
        "tasks": lambda result: format_task_list(result),  # Custom table renderer
    }

def get_empty_response(self, subdomain: str) -> str:
    return {
        "tasks": "No tasks found. Create one with 'add task: [title]'.",
        "sprints": "No sprints yet. Start one with 'create sprint'.",
        "projects": "No projects. Say 'new project: [name]' to begin.",
    }.get(subdomain, "Nothing found.")
```

### 2.4 Data Formatting

These control how records and entities appear in prompts (to the LLM) and in responses (to the user):

| Method | Context | What It Controls |
|--------|---------|------------------|
| `format_entity_for_context(type, ref, label, data, ...)` | LLM prompts | How entities display in the "Active Entities" section of Act. Rich formatting here improves LLM decisions. |
| `format_records_for_context(records, table)` | LLM prompts | How lists of DB records appear in step results. |
| `format_record_for_context(record, table)` | LLM prompts | Single-record formatting within the above. |
| `format_records_for_reply(records, table_type, indent)` | User replies | Domain-specific formatting for user-facing replies. |
| `get_priority_fields()` | User replies | Fields shown first when formatting records. |
| `get_strip_fields(context)` | Both | Fields hidden from prompts (`"injection"`) or user replies (`"reply"`). |

**Example — CRM stripping internal fields:**
```python
def get_strip_fields(self, context: str) -> set[str]:
    always_strip = {"created_at", "updated_at", "user_id"}
    if context == "reply":
        # Don't show internal scoring to end users
        return always_strip | {"lead_score", "health_score", "internal_notes"}
    return always_strip  # LLM can see scores for better reasoning
```

### 2.5 Entity Labels and Names

| Method | What It Controls |
|--------|------------------|
| `compute_entity_label(record, type, ref)` | *(abstract)* Human-readable label when registering a new entity (e.g., `"Acme Corp - $50K Deal"`) |
| `compute_entity_label_from_fks(type, fk_labels, ref)` | Compose labels from FK relationships (e.g., `"Task: Fix Login → Sprint 12"`) |
| `compute_artifact_label(artifact, entity_type, index)` | Label for generated `gen_*` refs before they're saved |
| `get_bold_skip_words()` | Headings to skip when extracting entity names from bold markdown |

---

## Part 3: Execution & Capabilities — What the System Can Do

These injections define what tools are available, what data the system can access, how CRUD works, and what modes are supported.

### 3.1 Subdomains — Scoping the Problem Space

Subdomains are the fundamental organizational unit. Each subdomain groups related tables and gives Think a clear scope for planning steps.

```python
@dataclass
class SubdomainDefinition:
    name: str                          # "deals", "contacts", "pipeline"
    primary_table: str                 # "deals"
    related_tables: list[str] = []     # ["deal_activities", "deal_notes"]
    description: str = ""              # For Think's planning context
```

**The power of subdomains:** They scope _everything_. When Think plans a step targeting the `deals` subdomain, Act receives only the deals schema, deals-specific examples, and deals-related entity context. This prevents cross-contamination and keeps prompts focused.

**Example — CRM domain subdomains:**
```python
@property
def subdomains(self) -> list[SubdomainDefinition]:
    return [
        SubdomainDefinition(
            name="contacts",
            primary_table="contacts",
            related_tables=["contact_emails", "contact_phones", "contact_tags"],
            description="People and companies. The foundation — deals and activities link here.",
        ),
        SubdomainDefinition(
            name="deals",
            primary_table="deals",
            related_tables=["deal_activities", "deal_notes", "deal_products"],
            description="Sales opportunities. Track from lead to close.",
        ),
        SubdomainDefinition(
            name="pipeline",
            primary_table="pipeline_stages",
            related_tables=["pipeline_rules"],
            description="Sales process stages and automation rules.",
        ),
        SubdomainDefinition(
            name="reports",
            primary_table="report_configs",
            related_tables=[],
            description="Saved report definitions and scheduling.",
        ),
    ]
```

**`get_subdomain_aliases()`** maps approximate names from the LLM to canonical subdomain names. The LLM might say "opportunities" when it means "deals" — this catches that:

```python
def get_subdomain_aliases(self) -> dict[str, str]:
    return {
        "opportunities": "deals",
        "people": "contacts",
        "companies": "contacts",
        "sales_process": "pipeline",
    }
```

### 3.2 Entities — What the System Tracks

Entities are the things users create, reference, and modify across turns. Each entity type maps to a database table and has tracking behavior configured through `EntityDefinition`.

```python
@dataclass
class EntityDefinition:
    type_name: str         # Short ref prefix: "deal" → deal_1, deal_2
    table: str             # DB table: "deals"
    primary_field: str     # Display field: "name"
    fk_fields: list[str]   # FK columns: ["contact_id", "pipeline_stage_id"]
    complexity: str | None  # Think hint: "high", "medium", None
    label_fields: list[str] # Label computation: ["name"] or ["date", "type"]
    nested_relations: list[str] | None  # Related tables to include in reads
    detail_tracking: bool   # Track summary vs full read levels
```

**Example — Project Management domain entities:**
```python
@property
def entities(self) -> list[EntityDefinition]:
    return [
        EntityDefinition(
            type_name="project",
            table="projects",
            primary_field="name",
            fk_fields=[],
            complexity="high",
            label_fields=["name"],
            nested_relations=["project_members"],
            detail_tracking=True,   # Distinguish "list of projects" vs "full project detail"
        ),
        EntityDefinition(
            type_name="task",
            table="tasks",
            primary_field="title",
            fk_fields=["project_id", "assignee_id", "sprint_id"],
            complexity="medium",
            label_fields=["title"],
            nested_relations=["task_comments"],
        ),
        EntityDefinition(
            type_name="sprint",
            table="sprints",
            primary_field="name",
            fk_fields=["project_id"],
            complexity="medium",
            label_fields=["name", "start_date"],
        ),
    ]
```

**Entity-related methods:**

| Method | What It Controls |
|--------|------------------|
| `infer_entity_type_from_artifact(artifact)` | *(abstract)* When Act generates content, what entity type is it? |
| `infer_table_from_record(record)` | Identify which table a record came from by its field structure. |
| `get_entity_data_legend(entity_type)` | Legend text for detail-tracking entities (explains summary vs full). |
| `detect_detail_level(entity_type, record)` | Classify whether a read result is summary or full detail. |

### 3.3 Step Types — The Four Execution Patterns

Every step in a plan uses one of four patterns. Two are tightly coupled to Postgres CRUD. Two are open-ended.

```
┌─────────────────────────────────────────────────────────────┐
│                    TIGHT COUPLING (Postgres)                 │
│                                                              │
│  READ ───── db_read tool ──────── Query with filters         │
│  WRITE ──── db_create/update/delete ── Mutate records        │
│                                                              │
│  Reliable, mechanical. The LLM constructs queries and        │
│  payloads; core executes them against your Postgres tables.  │
├─────────────────────────────────────────────────────────────┤
│                   OPEN-ENDED (Domain Tools)                  │
│                                                              │
│  ANALYZE ── Domain-configurable tools ── Reason over data    │
│  GENERATE ─ Domain-configurable tools ── Produce artifacts   │
│                                                              │
│  By default: no tools (LLM reasons in context only).         │
│  With custom tools: call Python functions, external APIs,    │
│  run computations — anything your handler implements.        │
└─────────────────────────────────────────────────────────────┘
```

**Read and Write** use built-in CRUD tools (`db_read`, `db_create`, `db_update`, `db_delete`) that map directly to Postgres operations through the `DatabaseAdapter`. They are mechanical — the LLM constructs the query parameters, and the CRUD executor runs them reliably.

**Analyze and Generate** are where domains get creative. By default they have no tools — the LLM reasons purely from data already in context (prior step results, entity data, user profile). But when you register custom tools and enable them for these step types, they become arbitrarily powerful.

### 3.4 Custom Tools — Extending Analyze and Generate

Custom tools let a domain give the LLM capabilities beyond CRUD. Two methods control this:

| Method | Default | What It Controls |
|--------|---------|------------------|
| `get_custom_tools()` | `{}` | Tool definitions + handlers. `dict[str, ToolDefinition]` |
| `get_tool_enabled_step_types()` | `{"read", "write"}` | Which step types have tool access at all. Override to include `"analyze"` and/or `"generate"`. |

```python
@dataclass
class ToolDefinition:
    name: str              # Tool name the LLM emits (e.g., "run_python")
    description: str       # One-line description for the LLM prompt
    params_schema: str     # Human-readable param docs
    handler: Callable      # async (params, user_id, context) -> Any
```

**The key unlock:** When `get_tool_enabled_step_types()` includes `"analyze"`, any analyze step in the plan gets tool access. The LLM can call your custom tools to compute, fetch, or transform data — then use the results to complete the step.

**Example — CRM domain with a Python analysis tool:**
```python
def get_tool_enabled_step_types(self) -> set[str]:
    return {"read", "write", "analyze"}  # Analyze steps can now call tools

def get_custom_tools(self) -> dict[str, ToolDefinition]:
    return {
        "run_analysis": ToolDefinition(
            name="run_analysis",
            description="Run a Python analysis function on deal data",
            params_schema="""
            {
              "function": "pipeline_conversion_rate | deal_velocity | revenue_forecast",
              "params": { "period": "30d | 90d | 1y", "stage": "optional stage filter" }
            }""",
            handler=self._handle_analysis,
        ),
    }

async def _handle_analysis(self, params, user_id, context):
    fn = params["function"]
    if fn == "pipeline_conversion_rate":
        # Run actual computation on deal data
        return {"conversion_rate": 0.23, "by_stage": {...}}
    elif fn == "deal_velocity":
        return {"avg_days_to_close": 34, "trend": "improving"}
```

**Example — Payments domain with an email generator tool:**
```python
def get_tool_enabled_step_types(self) -> set[str]:
    return {"read", "write", "generate"}  # Generate steps can call tools

def get_custom_tools(self) -> dict[str, ToolDefinition]:
    return {
        "draft_email": ToolDefinition(
            name="draft_email",
            description="Generate a professional email from a template",
            params_schema="""
            {
              "template": "invoice_reminder | payment_receipt | subscription_renewal",
              "recipient_id": "contact UUID ref",
              "variables": { "amount": "...", "due_date": "...", ... }
            }""",
            handler=self._handle_draft_email,
        ),
        "calculate_proration": ToolDefinition(
            name="calculate_proration",
            description="Calculate prorated amount for subscription changes",
            params_schema='{ "subscription_ref": "...", "new_plan": "...", "effective_date": "..." }',
            handler=self._handle_proration,
        ),
    }
```

**Reply vs. Generate — when does output go to the user vs. somewhere else?**

The pipeline always ends with Reply, which formats the final response for the user. But the _content_ generated in a `generate` step doesn't have to be "a reply" — it can be an email draft, a report, an invoice, a sprint plan. Reply's job is to _present_ that generated content appropriately:

```
User: "Send a payment reminder to Acme Corp"

Think plans:
  1. read(contacts) → Find Acme Corp contact
  2. read(invoices) → Find overdue invoices
  3. generate(invoices) → Draft reminder email using draft_email tool
  4. write(emails) → Save email to outbox (pending user confirmation)

Reply presents:
  "Here's the payment reminder I drafted for Acme Corp:
   [formatted email preview]
   Ready to send? Say 'send it' to confirm."
```

Generate produces the artifact. Reply presents it. Write persists it. The `gen_*` → real ref promotion ensures nothing is saved without user confirmation.

### 3.5 CRUD Configuration — Database Access

These methods configure how the built-in CRUD tools interact with your Postgres tables.

| Method | What It Controls |
|--------|------------------|
| `get_db_adapter()` | *(abstract)* The database client. Returns a `DatabaseAdapter` (PostgREST-compatible). |
| `get_user_owned_tables()` | *(abstract)* Tables that get automatic `user_id` filter injection for security scoping. |
| `get_uuid_fields()` | *(abstract)* FK fields where `""` is sanitized to `None` before insert. |
| `get_fk_field_aliases()` | Maps non-standard FK names to standard equivalents. |
| `get_fk_enrich_map()` | FK enrichment for entity labels: `{"contact_id": ("contacts", "name")}`. |
| `get_subdomain_registry()` | Subdomain → table mapping for schema introspection. |
| `get_field_enums()` | *(abstract)* Enum field values injected into schema context. |
| `get_semantic_notes()` | *(abstract)* Field-level notes for the LLM (e.g., "amount is in cents"). |

**Example — Payments domain CRUD config:**
```python
def get_user_owned_tables(self) -> list[str]:
    return ["invoices", "subscriptions", "payouts", "payment_methods"]

def get_fk_enrich_map(self) -> dict:
    return {
        "customer_id": ("customers", "company_name"),
        "subscription_id": ("subscriptions", "plan_name"),
    }

def get_field_enums(self) -> dict:
    return {
        "invoices.status": ["draft", "sent", "paid", "overdue", "void"],
        "subscriptions.interval": ["monthly", "quarterly", "annual"],
        "payouts.method": ["bank_transfer", "check", "crypto"],
    }

def get_semantic_notes(self) -> dict:
    return {
        "invoices.amount_cents": "Amount in cents (divide by 100 for display)",
        "invoices.due_date": "ISO date. Overdue = due_date < today AND status != 'paid'",
        "subscriptions.current_period_end": "When the current billing period ends",
    }
```

### 3.6 CRUD Middleware — Hooks Around Every Operation

`CRUDMiddleware` lets you intercept every CRUD operation with pre/post hooks:

| Hook | When | What It Can Do |
|------|------|----------------|
| `pre_read(params, user_id, context)` | Before `db_read` | Rewrite filters, add nested relations, inject semantic search, short-circuit empty |
| `post_read(records, table, user_id, context)` | After `db_read` | Transform results, enrich records, filter sensitive fields |
| `pre_write(params, user_id, context)` | Before `db_create`/`db_update` | Validate, transform, add computed fields |
| `deduplicate_batch(items, table, user_id)` | Before batch `db_create` | Prevent duplicate creation |

**Example — CRM middleware that adds semantic search:**
```python
class CRMMiddleware(CRUDMiddleware):
    async def pre_read(self, params, user_id, context):
        # If searching contacts by name, also do fuzzy match
        if params.table == "contacts" and has_name_filter(params):
            fuzzy_ids = await self.semantic_search(params, user_id)
            return ReadPreprocessResult(
                params=params,
                pre_filter_ids=fuzzy_ids,  # Results filtered to these IDs
            )
        return ReadPreprocessResult(params=params)
```

### 3.7 Modes — Controlling the Pipeline

Three core modes control pipeline behavior. Domains don't define these — they configure them.

| Mode | Max Steps | Skip Think? | Proposal Required? | Verbosity | Best For |
|------|----------|------------|-------------------|-----------|----------|
| **QUICK** | 2 | Yes | No | Terse | "Show my tasks", "Add a contact" |
| **PLAN** | 8 | No | Yes | Detailed | Multi-step workflows, complex queries |
| **CREATE** | 4 | No | No | Rich | Generation tasks, content creation |

Mode is selected by the user (UI toggle or CLI flag), with a profile default as fallback.

### 3.8 Bypass Modes — Skipping the Graph Entirely

Domains can register modes that bypass the LangGraph pipeline completely. These are for specialized interactions that don't fit the read/analyze/generate/write pattern.

| Method | What It Controls |
|--------|------------------|
| `bypass_modes` | *(abstract property)* `dict[str, type]` — mode name → handler class. |
| `get_mode_llm_config()` | LLM config overrides for bypass modes (e.g., different model, temperature). |
| `get_handoff_system_prompts()` | System prompts for summarizing bypass mode sessions back into main conversation. |
| `get_handoff_result_model()` | *(abstract)* Pydantic model for bypass mode handoff data. |

**Example — CRM domain with a "discovery call" bypass mode:**
```python
@property
def bypass_modes(self) -> dict[str, type]:
    return {
        "discovery": DiscoveryCallMode,  # Guided call script, no CRUD pipeline needed
    }
```

Bypass modes run their own LLM calls, manage their own state, and hand back a summary to the main conversation when done. They're useful for guided flows, interactive sessions, or conversational patterns that don't decompose into discrete steps.

### 3.9 Payload Compilers — Generate → Write Normalization

When a `generate` step produces structured content, it often needs to be transformed into database-ready payloads before a `write` step can save it.

| Method | What It Controls |
|--------|------------------|
| `get_payload_compilers()` | `list[SubdomainCompiler]` — transforms generated artifacts into CRUD-ready payloads. |

**Example — Project Management domain:**
A `generate` step might produce a sprint plan as structured JSON. The payload compiler normalizes it into `sprints` + `sprint_tasks` records ready for `db_create`.

---

## Part 4: What to Change First

### Starting a New Domain — Minimum Viable Configuration

These are the abstract methods you _must_ implement. Everything else has defaults.

```python
class MyDomain(DomainConfig):
    # Identity
    name = "my_domain"

    # Structure (define your data model)
    entities = [...]              # EntityDefinitions
    subdomains = [...]            # SubdomainDefinitions
    bypass_modes = {}             # Can be empty
    default_agent = "my_agent"    # Agent name for routing

    # Database
    def get_db_adapter(self): ...
    def get_user_owned_tables(self): ...
    def get_uuid_fields(self): ...
    def get_subdomain_registry(self): ...

    # Schema context
    def get_fallback_schemas(self): ...  # Keyed by SUBDOMAIN name
    def get_field_enums(self): ...
    def get_semantic_notes(self): ...

    # Per-step content
    def get_persona(self, subdomain, step_type): ...
    def get_examples(self, subdomain, step_type, desc, prev): ...

    # Entity lifecycle
    def compute_entity_label(self, record, type, ref): ...
    def infer_entity_type_from_artifact(self, artifact): ...

    # Data formatting
    def get_table_format(self, table): ...
    def get_empty_response(self, subdomain): ...
    def get_subdomain_formatters(self): ...
    def get_subdomain_aliases(self): ...

    # Modes
    def get_handoff_result_model(self): ...
```

### Highest-Impact Overrides (Do These Next)

| Priority | Method | Why |
|----------|--------|-----|
| 1 | `get_examples()` | Most impactful single method. Good examples = good execution. |
| 2 | `get_system_prompt()` | Defines who the assistant is. Affects every reply. |
| 3 | `get_think_planning_guide()` | Teaches Think how subdomains relate and what patterns to use. |
| 4 | `get_act_subdomain_header()` | Scopes each execution step. Keeps the LLM focused. |
| 5 | `get_user_profile()` | Enables personalization across all nodes. |
| 6 | `format_entity_for_context()` | Richer entity display = better LLM decisions. |

### When to Graduate to Full Prompt Replacement

Use the template + injection approach until you see specific failure patterns:

| Symptom | Solution |
|---------|----------|
| Think plans wrong step types | Override `get_think_prompt_content()` with explicit step-type guidance |
| Act misunderstands CRUD patterns | Override `get_act_step_template("read")` or `get_act_step_template("write")` |
| Reply formats data awkwardly | Override `get_reply_prompt_content()` with domain-specific formatting rules |
| Quick mode misclassifies requests | Override `get_understand_prompt_content()` with domain-specific quick-mode table |

### Adding Tool Capabilities

```
Step 1: Define your tools
   └── get_custom_tools() → dict[str, ToolDefinition]

Step 2: Enable them for the right step types
   └── get_tool_enabled_step_types() → {"read", "write", "analyze"}

Step 3: Write handler functions
   └── async def handler(params, user_id, context) -> Any

Step 4: Add tool docs to Act prompts
   └── Automatic — core injects tool descriptions from ToolDefinition
```

---

## Appendix: Full Method Reference (Alphabetical)

Quick-lookup table. Every `DomainConfig` method, which node consumes it, and whether it's abstract (must implement) or has a default.

| Method | Node(s) | Abstract? | Category |
|--------|---------|-----------|----------|
| `agents` | Workflow | No (default: `[]`) | Execution |
| `agent_router` | Workflow | No (default: `None`) | Execution |
| `bypass_modes` | Workflow | **Yes** | Execution |
| `compute_artifact_label()` | Act | No | UI |
| `compute_entity_label()` | Act | **Yes** | UI |
| `compute_entity_label_from_fks()` | Act | No | UI |
| `default_agent` | Workflow | **Yes** | Execution |
| `detect_detail_level()` | Act | No | Reasoning |
| `entities` | Workflow, Act, Summarize | **Yes** | Execution |
| `format_entity_for_context()` | Act | No | Reasoning |
| `format_record_for_context()` | Act | No | Reasoning |
| `format_records_for_context()` | Act | No | Reasoning |
| `format_records_for_reply()` | Reply | No | UI |
| `get_act_prompt_content()` | Act | No | Reasoning |
| `get_act_prompt_injection()` | Act | No | Reasoning |
| `get_act_step_template()` | Act | No | Reasoning |
| `get_act_subdomain_header()` | Act | No | Reasoning |
| `get_archive_key_for_description()` | Act | No | Execution |
| `get_archive_keys_for_subdomain()` | Act | No | Execution |
| `get_bold_skip_words()` | Reply | No | UI |
| `get_crud_middleware()` | Act | No | Execution |
| `get_crud_reference()` | Act | No | Reasoning |
| `get_custom_tools()` | Act | No | Execution |
| `get_db_adapter()` | Act | **Yes** | Execution |
| `get_domain_snapshot()` | Think, Act | No | Reasoning |
| `get_empty_response()` | Reply | **Yes** | UI |
| `get_entity_data_legend()` | Act | No | UI |
| `get_entity_recency_window()` | Act | No | Reasoning |
| `get_examples()` | Act | **Yes** | Reasoning |
| `get_fallback_schemas()` | Act | **Yes** | Execution |
| `get_field_enums()` | Act | **Yes** | Execution |
| `get_filter_schema()` | Act | No | Reasoning |
| `get_fk_enrich_map()` | Act | **Yes** | Execution |
| `get_fk_field_aliases()` | Act | No | Execution |
| `get_generated_content_label()` | Summarize | No | UI |
| `get_generated_content_markers()` | Summarize | No | UI |
| `get_handoff_result_model()` | Workflow | **Yes** | Execution |
| `get_handoff_system_prompts()` | Workflow | No | Reasoning |
| `get_mode_llm_config()` | Workflow | No | Execution |
| `get_payload_compilers()` | Act | No | Execution |
| `get_persona()` | Act Quick | **Yes** | Reasoning |
| `get_priority_fields()` | Reply | No | UI |
| `get_quick_write_confirmation()` | Reply | No | UI |
| `get_relevant_entity_types()` | Act, Reply | No | Reasoning |
| `get_reply_prompt_content()` | Reply | No | Reasoning |
| `get_reply_subdomain_guide()` | Reply | No | Reasoning |
| `get_router_prompt_injection()` | Router | No | Reasoning |
| `get_scope_config()` | Act | No | Execution |
| `get_semantic_notes()` | Act | **Yes** | Execution |
| `get_strip_fields()` | Act, Reply | No | UI |
| `get_subdomain_aliases()` | Act | **Yes** | Execution |
| `get_subdomain_examples()` | Think | **Yes** | Reasoning |
| `get_subdomain_formatters()` | Reply | **Yes** | UI |
| `get_subdomain_guidance()` | Think, Act | No | Reasoning |
| `get_subdomain_registry()` | Act | **Yes** | Execution |
| `get_summarize_system_prompts()` | Summarize | No | Reasoning |
| `get_system_prompt()` | Reply | No | UI |
| `get_table_format()` | Act | **Yes** | UI |
| `get_think_domain_context()` | Think | No | Reasoning |
| `get_think_planning_guide()` | Think | No | Reasoning |
| `get_think_prompt_content()` | Think | No | Reasoning |
| `get_tool_enabled_step_types()` | Act | No | Execution |
| `get_tracked_entity_types()` | Act | No | Reasoning |
| `get_understand_prompt_content()` | Understand | No | Reasoning |
| `get_understand_system_prompt()` | Understand | No | Reasoning |
| `get_user_owned_tables()` | Act | **Yes** | Execution |
| `get_user_profile()` | Think, Act | No | Reasoning |
| `get_uuid_fields()` | Act | **Yes** | Execution |
| `infer_entity_type_from_artifact()` | Act | **Yes** | Execution |
| `infer_table_from_record()` | Act | No | Execution |
| `name` | Workflow, Reply | **Yes** | UI |
| `subdomains` | Think, Act | **Yes** | Execution |

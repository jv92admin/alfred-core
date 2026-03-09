# Alfred Domain Design Guide

> You are designing a new domain for Alfred's orchestration engine. This document
> teaches you how Alfred works at a design level so you can make informed decisions
> about entities, subdomains, CRUD patterns, and prompts. It uses the existing
> Kitchen domain as a worked example throughout.

---

## What Alfred Is

Alfred is an LLM-powered conversational assistant that talks to a database. Users
say things in natural language; Alfred plans what data to read/write, executes it,
and replies naturally.

It runs a 5-stage pipeline:

```
UNDERSTAND → THINK → ACT (loop) → REPLY → SUMMARIZE
```

- **Understand** — Resolves references ("that player" → `player_1`), curates which
  entities stay in context, detects if a simple query can skip planning
- **Think** — Plans execution steps: what to read, write, analyze, or generate
- **Act** — Executes each planned step via database CRUD or LLM generation. Loops
  through all steps in the plan.
- **Reply** — Synthesizes a natural language response from execution results
- **Summarize** — Compresses context for the next conversational turn

Alfred is split into two layers:

- **Core** — The pipeline, entity tracking, CRUD execution, prompt assembly,
  conversation memory. Completely domain-agnostic. You never modify this.
- **Domain** — Your implementation. Entities, subdomains, personas, database
  adapter, domain-specific prompts. This is what you're designing.

Core doesn't know what "players" or "recipes" are. It knows how to plan, execute
CRUD, track entities, and hold conversations. Your domain tells it *what things
exist* and *how to talk about them*.

---

## How Subdomains Shape the User Experience

### What Subdomains Are

A subdomain is a logical grouping of database tables around a user-facing concern.
It's NOT a technical abstraction — it's a UX concept. Subdomains answer: "What
activity is the user doing right now?"

**Kitchen example:**

| Subdomain | Primary Table | Related Tables | What Users Do Here |
|-----------|--------------|----------------|-------------------|
| recipes | `recipes` | `recipe_ingredients`, `ingredients` | Search recipes, view details, save generated recipes |
| inventory | `inventory` | `ingredients` | Check what's in the pantry, add/remove items |
| shopping | `shopping_list` | `ingredients` | Build shopping lists, check off items |
| meal_plans | `meal_plans` | `recipes`, `tasks` | Plan weekly meals, assign recipes to days |
| tasks | `tasks` | `recipes`, `meal_plans` | Cooking tasks, prep reminders |
| preferences | `preferences` | `flavor_preferences` | Dietary restrictions, cuisine preferences |
| history | `cooking_log` | — | What they've cooked recently |

### How Subdomains Affect the Pipeline

**Think uses subdomains to plan.** When a user says "find me a chicken recipe and
add chicken to my shopping list," Think creates two steps:

```
Step 1: READ in subdomain "recipes" — search for chicken recipes
Step 2: WRITE in subdomain "shopping" — add chicken to shopping list
```

Each step targets exactly ONE subdomain. The subdomain determines which tables the
step can access and which persona/examples the LLM gets.

**The subdomain description matters.** It gets injected into the Think prompt. This
means your description directly influences how the LLM plans:

```
# Weak description — Think doesn't know when to route here
"Squad management."

# Strong description — Think understands the scope and routing signals
"Squad management. View current squad, check formation,
 assess team value. Users say: 'show my team', 'who's in my squad',
 'what's my team value'."
```

**Cross-subdomain access is controlled by table lists.** Each subdomain declares
which tables it can access in the subdomain registry. A table can appear in
multiple subdomains — that's how cross-cutting workflows work. For example, if a
"shopping" step needs recipe data, the `recipes` table is listed in both the
`recipes` subdomain AND the `shopping` subdomain:

```python
# Kitchen example — subdomain registry
"shopping": {"tables": ["shopping_list", "recipes", "inventory"]},
"meal_plans": {"tables": ["meal_plans", "recipes"]},
```

Each step targets one subdomain, and can access any table listed in that
subdomain's registry entry.

### Design Principle: Subdomains Should Map to User Intent, Not Database Schema

Bad: grouping by database structure ("player_data", "reference_tables")
Good: grouping by what the user is trying to do ("squad_management", "transfers",
"analysis")

The Think node needs to match user intent to subdomains. If a user says "who should
I captain?" — Think needs a subdomain that clearly handles captaincy decisions.

---

## How Entities and Refs Work

### The Ref System

Users and LLMs never see database UUIDs. Alfred translates every UUID into a
human-readable ref:

```
Database:  a508000d-9b55-40f0-8886-dbdd88bd2de2
LLM sees:  recipe_1
User sees: "Butter Chicken" (the label)
```

Refs follow the pattern `{type}_{n}`:
- `recipe_1`, `recipe_2`, `recipe_3`
- `inv_1`, `inv_2`
- `player_1`, `team_3`, `transfer_2`

The `type` comes from your entity definition's `type_name` field. Keep type names
short — they appear frequently in prompts.

**Refs persist across turns.** `recipe_1` on turn 1 is the same entity on turn 5.
The user can say "that recipe" or "the first one" and Understand resolves it back to
`recipe_1`.

### Generated Content Gets Special Refs

When the LLM generates content (e.g., "suggest a recipe"), it gets a `gen_` prefixed
ref:

```
gen_recipe_1 — exists only in memory, not yet in the database
```

When the user says "save it," the generated content gets written to the database and
`gen_recipe_1` is promoted to a real ref pointing at the new UUID. This "generate
now, save later" pattern means users always approve before anything hits the DB.

### FK Enrichment: How Related Entities Display

When a record has a foreign key (e.g., `recipe_id` on a meal plan), Alfred enriches
it with a human-readable label:

```
Raw from DB:    {"recipe_id": "a508000d-...", "day": "Monday"}
After enrichment: {"recipe_id": "recipe_3", "_recipe_id_label": "Butter Chicken", "day": "Monday"}
```

This means the LLM sees `recipe_3 (Butter Chicken)` instead of a UUID. For this to
work, you define an FK enrichment map:

```python
# Kitchen example
{
    "recipe_id": ("recipes", "name"),      # Look up name in recipes table
    "ingredient_id": ("ingredients", "name"),
}
```

### Entity Labels

Each entity gets a human-readable label computed by your domain. Labels appear in
prompts and context:

```
- recipe_1: Butter Chicken (recipe) [read:full]
- inv_5: Chicken Breast (inventory) [read:summary]
- gen_recipe_1: Suggested Thai Curry (recipe) [unsaved]
```

Your `compute_entity_label()` function determines how labels are computed from
record fields. Make labels instantly recognizable — they're how the LLM (and user)
identify entities.

### Detail Tracking

Some entities have "summary" vs "full" detail levels. For example, a recipe search
might return just names and cook times (summary), while viewing a specific recipe
returns the full record with ingredients (full).

The Think node sees detail levels and plans accordingly:

```
recipe_1: Butter Chicken [read:summary] — Think knows to plan a full read if
                                          the user wants ingredients
recipe_2: Pasta Carbonara [read:full]   — Think skips redundant read
```

This prevents wasteful re-reads and helps the LLM know what data it actually has.

---

## CRUD: What Operations Mean at the UX Level

Alfred has four CRUD operations (read, write, update, delete) plus two LLM-only
operations (analyze, generate). Understanding what they abstract to at the user
experience level is critical for good subdomain design.

### READ — "Show me things"

Read is the most common operation. It's how the LLM gets data to reason about.

**What happens:**
1. Think plans a read step with a goal: "Find chicken recipes under 30 minutes"
2. Act constructs a database query with filters: `table: recipes, filters: [{field: cook_time_minutes, op: lte, value: 30}, {field: name, op: ilike, value: "%chicken%"}]`
3. CRUD executes the query, translates UUIDs to refs, enriches FK labels
4. Results go back to Act for the next step (or to Reply if done)

**Available filter operators:**
`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike` (case-insensitive),
`in` (list), `is` (null check), `contains` (array/JSON), `overlaps` (array overlap),
`similar` (semantic search — requires domain middleware `CRUDMiddleware.pre_read()`)

**User-owned tables get auto-scoped.** If you mark a table as user-owned, every read
automatically filters by `user_id`. The user only sees their own data. Reference
tables (shared data like players, ingredients) don't get this scoping.

**Built-in aggregates.** `db_read` supports `aggregate` mode for scalar queries —
the LLM can ask "how many?", "total of?", "average?" without fetching all rows.
Set `aggregate` to `count`, `sum`, `avg`, or `count_distinct`, plus `aggregate_field`
for sum/avg/count_distinct. Filters apply as WHERE before aggregation. Results are
single-row scalars like `[{"count": 42}]` — no entity refs, no registry tracking.

```
"How many active recipes do I have?"
  → db_read: table="recipes", filters=[status=active], aggregate="count"
  → [{"count": 15}]

"What's my total inventory quantity?"
  → db_read: table="inventory", aggregate="sum", aggregate_field="quantity"
  → [{"sum": 340}]
```

**Smart reads via RPCs.** For more complex aggregation (GROUP BY, multi-table joins,
ranking), the database adapter supports RPCs (stored procedures). A READ step can
call a pre-built function that returns pre-computed data. This is the line of defense
for queries that go beyond what simple aggregates cover.

```
"Show top midfielders by expected goals this season"
  → READ calls: top_players_by_metric('xGI', 'MID', 6, 20)
  → Returns 20 pre-aggregated rows, not 200+ raw player records
```

Design your RPCs around common query patterns in your domain. This keeps READ
fast and ANALYZE focused on interpretation rather than computation.

**Kitchen examples of read patterns by subdomain:**

| Subdomain | User Says | What Read Does |
|-----------|-----------|---------------|
| recipes | "find pasta recipes" | Search recipes by name/tags, return summary (name, cook_time, cuisine) |
| recipes | "show me recipe_1" | Full read with nested recipe_ingredients included |
| inventory | "what's in my fridge?" | Read all inventory items for user, enriched with ingredient names |
| shopping | "show my shopping list" | Read shopping_list for user, grouped by category |
| meal_plans | "what's for dinner this week?" | Read meal_plans filtered by date range, FK-enriched with recipe names |

### WRITE / CREATE — "Save this" or "Add that"

Write creates new records or updates existing ones.

**Key behaviors:**
- **Ref translation:** If the LLM says "create a meal plan with recipe_3", CRUD
  translates `recipe_3` back to its UUID before writing
- **User-owned tables:** `user_id` is automatically injected — the LLM never needs
  to specify it
- **Batch operations:** Multiple records can be created in one step (e.g., adding
  5 items to a shopping list)

**Kitchen write patterns:**

| Subdomain | User Says | What Write Does |
|-----------|-----------|----------------|
| inventory | "add chicken and rice" | Create 2 inventory records, resolve ingredient names to IDs |
| shopping | "add recipe_1 ingredients to my list" | Batch create shopping_list records from recipe_ingredients |
| meal_plans | "plan recipe_3 for Monday dinner" | Create meal_plan record with recipe_id FK |

### UPDATE — "Change this"

Update modifies existing records. The LLM references entities by ref.

**Kitchen update patterns:**

| Subdomain | User Says | What Update Does |
|-----------|-----------|-----------------|
| inventory | "I used half the chicken" | Update inventory quantity for inv_5 |
| shopping | "mark chicken as bought" | Update shopping_list status field |

### DELETE — "Remove this"

Delete removes records. Generally limited to user-owned tables.

**Kitchen delete patterns:**

| Subdomain | User Says | What Delete Does |
|-----------|-----------|-----------------|
| inventory | "remove the expired milk" | Delete inventory record for inv_3 |
| shopping | "clear my shopping list" | Delete all shopping_list records for user |

### ANALYZE — "What does this mean?"

ANALYZE is NOT a CRUD operation — it makes no database calls. It's "reason about
data already in context." The LLM receives results from previous READ steps and
produces analysis, comparisons, or recommendations.

**What happens:**
1. Think plans an analyze step with a goal: "Compare these midfielders by form
   and fixture difficulty"
2. Act receives the data from earlier read steps in its context
3. The LLM reasons about the data — compares, ranks, identifies patterns
4. The analysis output goes to the next step or to Reply

**Kitchen analyze patterns:**

| Subdomain | User Says | What Analyze Does |
|-----------|-----------|------------------|
| recipes | "which of these is easiest?" | Compare recipe complexity from read results |
| meal_plans | "is my week balanced?" | Evaluate nutritional variety across the week's meal plans |
| inventory | "what can I make with what I have?" | Cross-reference inventory with recipe ingredients |

**Why this matters for design:** ANALYZE steps are where your domain's expertise
shines. FPL's most valuable conversations will be analysis: "compare these
midfielders", "is my defense good enough?", "which transfers give the best value?"
The persona and semantic notes you provide directly shape analysis quality.

**ANALYZE with tool calling.** By default, ANALYZE is pure LLM reasoning (no database
calls). Domains that need mid-analysis data fetching can override
`get_tool_enabled_step_types()` to include `"analyze"` — this gives ANALYZE steps
full CRUD tool access (schema, db_read, etc.). When designing your domain, note which
analysis patterns would benefit from additional data fetching vs. which are pure reasoning.
The same applies to GENERATE steps.

**Important naming note:** ANALYZE is a *step type* (what kind of work a step does).
Don't confuse it with subdomain names. If you have a subdomain called "analysis" and
a step type called "analyze", you'll end up with "ANALYZE step in subdomain analysis"
— legal but confusing. Consider alternative subdomain names like "stats", "scouting",
or "research" if your domain has analysis-heavy subdomains.

### GENERATE — "Create something new" / "Render the final output"

GENERATE is also NOT a CRUD operation — it produces structured content that lives
in memory as a pending artifact. GENERATE has two use cases:

1. **Content creation** (kitchen pattern): Generate a recipe → user reviews → save.
   The artifact awaits approval before persistence.
2. **Render / visualization** (analytics-heavy domains): Generate a structured
   display artifact (table spec, chart spec, comparison matrix) from READ/ANALYZE
   results. The frontend renders it immediately. Optionally saveable later.

**What happens:**
1. Think plans a generate step: "Generate a suggested wildcard squad"
2. Act produces structured content (JSON) — e.g., a full 15-player squad
3. The content gets a `gen_*` ref: `gen_squad_1`
4. Reply presents it to the user ("Here's my suggested squad...")
5. User can modify ("swap out the keeper") or approve ("save it")
6. If approved, a WRITE step saves it to the database

**Kitchen generate patterns:**

| Subdomain | User Says | What Generate Does |
|-----------|-----------|-------------------|
| recipes | "suggest a pasta recipe" | Produce a full recipe JSON (name, ingredients, instructions, times) → `gen_recipe_1` |
| meal_plans | "plan my week" | Produce 7 days of meal assignments → presented for approval |

**The generate → approve → save flow:**

```
Turn 1: "suggest a chicken recipe"
  → GENERATE: LLM produces recipe → gen_recipe_1 (in memory only)
  → REPLY: "Here's a recipe for Butter Chicken: ..."

Turn 2: "looks good, save it"
  → WRITE: Save gen_recipe_1 to recipes table → gets real UUID
  → WRITE: Save recipe_ingredients (linked records)
  → REPLY: "Saved! It's now recipe_4 in your collection."

Turn 2 (alternative): "make it vegetarian"
  → The pending artifact is updated in memory
  → REPLY: "Updated to use paneer instead..."

Turn 3: "now save it"
  → WRITE: Save the modified version
```

**Why this matters for design:** GENERATE serves two purposes depending on your
domain. For content-creation domains (kitchen), identify entities with a "suggest →
review → save" pattern. For analytics-heavy domains (FPL), GENERATE is your render
step — it structures data into display artifacts after READ and ANALYZE have done
the heavy lifting. The pipeline becomes:

```
READ (smart RPCs) → ANALYZE (interpret) → GENERATE (render) → Reply (commentate)
```

In the render pattern, Reply doesn't repeat the data — it provides insight and
commentary on what GENERATE already structured for display. Think Jupyter notebook:
GENERATE is the code cell output, Reply is the markdown cell that explains it.

---

### CRUD Middleware: Domain Intelligence Layer

Middleware intercepts CRUD operations before they hit the database. It's optional
but powerful. This is how you add "smart" behavior.

**Kitchen middleware examples:**

| Behavior | What It Does |
|----------|-------------|
| Semantic search | "find Italian recipes" → pgvector similarity search, not just `ilike` |
| Auto-include | Reading a recipe auto-includes its `recipe_ingredients` as nested data |
| Fuzzy name matching | "add chicken" matches "Chicken Breast" in ingredients table |
| Ingredient enrichment | Creating inventory auto-resolves ingredient names to IDs |

Middleware is optional. Start without it — the basic CRUD works fine. Add it when
you find patterns where the LLM consistently constructs suboptimal queries.

---

## Linked Tables and Nested Relations

### The Pattern

Some entities are parents with child records. The canonical example:

```
recipes (parent)
  └── recipe_ingredients (children)
        └── ingredients (reference, FK from recipe_ingredients)
```

When you read a recipe, you usually want its ingredients too. Without configuration,
you'd need two separate reads. With nested relations, the recipe read auto-includes
its children:

```python
# Entity definition with nested relation
"recipes": EntityDefinition(
    type_name="recipe",
    table="recipes",
    primary_field="name",
    nested_relations=["recipe_ingredients"],  # Auto-include in reads
)
```

### How It Works in Practice

**Read:** User says "show me recipe_1" → CRUD reads the recipe AND its
recipe_ingredients in one query. The response includes:

```json
{
  "id": "recipe_1",
  "name": "Butter Chicken",
  "cook_time_minutes": 45,
  "recipe_ingredients": [
    {"ingredient_id": "ing_12", "_ingredient_id_label": "Chicken", "quantity": "500g"},
    {"ingredient_id": "ing_7", "_ingredient_id_label": "Butter", "quantity": "50g"}
  ]
}
```

**Write:** When saving a generated recipe, the CRUD layer handles both the parent
record AND its children in a batch. The recipe is created first (getting a real
UUID), then recipe_ingredients are created with that UUID as their FK.

### Design Considerations for Linked Tables

When designing your domain, ask:

1. **Which entities are parent-child?** (e.g., squad → squad_players, or
   transfer_plan → transfer_moves)
2. **Should children auto-include on read?** Only if they're always relevant.
   Don't auto-include large child sets.
3. **Are children independently addressable?** recipe_ingredients are always
   accessed through their parent recipe. But a player in a squad might also be
   accessed independently through the "analysis" subdomain.
4. **What FK fields connect them?** These go in `fk_fields` on the child entity.

---

## Modes: Quick vs Full Pipeline

### Quick Mode

Simple queries skip the Think → Act loop entirely:

```
"show my squad"     → QUICK: single read, immediate response
"what's my budget?" → QUICK: single read, immediate response
```

The Understand node detects quick-mode queries. It's triggered by simple,
unambiguous requests that need exactly one CRUD operation.

**Why this matters for design:** You should identify which queries in your domain
are "quick mode" candidates. These are your most common simple lookups. The
subdomain examples you provide (like "show my squad" → squad) help Understand
route correctly.

### Full Pipeline

Complex requests go through the full pipeline:

```
"plan my wildcard team"
  → THINK: Plans 4 steps
    Step 1: READ analysis — get top players by position
    Step 2: READ analysis — check fixture difficulty
    Step 3: ANALYZE — evaluate combinations within budget
    Step 4: GENERATE — produce squad suggestion
  → ACT: Executes each step
  → REPLY: Presents the suggested squad
```

**Why this matters for design:** Your subdomain structure needs to support
multi-step workflows. If "plan my wildcard" needs player stats, fixture data,
AND budget info, those tables need to be listed in the subdomain's table registry
(a table can appear in multiple subdomains).

### Modes: QUICK, PLAN, CREATE

Alfred has three execution modes that affect behavior:

| Mode | When | Behavior |
|------|------|----------|
| QUICK | Simple lookups | Skip Think, single CRUD call, immediate reply |
| PLAN | Multi-step requests | Full Think → Act loop, multiple steps |
| CREATE | Generation + approval | Like PLAN but includes generate steps, `gen_*` refs, approval flow |

---

## How Multi-Turn Conversations Work

Alfred is designed for iterative, multi-turn conversations — not one-shot queries.
Understanding this shapes how you design subdomains and entities.

**Entity persistence:** Entities from earlier turns stay in context. If turn 1 reads
5 players (`player_1` through `player_5`), turn 2 can reference them: "compare
player_1 and player_3" works without re-reading. The Understand node manages which
older entities stay active and which fall out of context (default: last 2 turns are
automatically active; older entities are kept if the LLM judges them still relevant).

**Iterative refinement:** Users naturally narrow down. "Show top scorers" → "just
midfielders" → "under 8 million" → "compare those two". Each turn builds on the
previous. Think sees previous step results and plans accordingly — the second query
doesn't re-read everything, it filters the existing context.

**Cross-turn references:** "That player", "the first one", "the cheap one" — these
all work. Understand resolves anaphoric references back to specific entity refs.
This means entity labels matter: if two players both show as just "player", the LLM
can't disambiguate "the first one" well. Good labels (web_name for FPL: "Salah",
"Haaland") make cross-turn references reliable.

**Complex workflows execute fully.** When Think plans a 4-step workflow, all 4 steps
execute before the user can redirect. The user sees streaming progress ("Reading
players... Analyzing fixtures... Generating squad...") but can't interrupt. Design
workflows as complete units — "plan my wildcard" should produce a finished suggestion,
not ask intermediate questions.

**Why this matters for design:** FPL conversations are naturally iterative. Design
your subdomains so that common follow-up patterns work: "show players" (read) →
"compare those two" (analyze) → "add the better one" (write) should flow across
subdomains without the user needing to re-specify context.

---

## Personas and Prompts

### How Personas Affect Conversation

Each subdomain gets a persona — a description of how the LLM should behave when
working in that area.

**Kitchen persona examples:**

```
recipes:   "You are a knowledgeable home cook and recipe curator. Focus on
            practical, achievable recipes. When searching, consider skill
            level, available time, and dietary preferences."

inventory: "You are a kitchen inventory manager. Be precise about quantities
            and units. Flag items that might be expired. Suggest using items
            that are close to expiring."

shopping:  "You are a smart shopping assistant. Group items by store section.
            Suggest quantities based on recipe needs. Flag items already in
            inventory."
```

**Why this matters:** The persona shapes HOW the LLM talks and WHAT it
prioritizes. A weak persona ("You help with transfers") produces generic
responses. A strong persona ("You are a transfer expert. Consider price changes,
fixture difficulty over the next 5 gameweeks, ownership percentage, and expected
points. Flag differential picks under 10% ownership.") produces domain-expert
responses.

### Examples Teach Patterns

Examples show the LLM concrete CRUD patterns for each subdomain. They're
especially important for teaching:

1. **Which table to query** — "show my squad" → `squad_selections`, not `players`
2. **Which filters to use** — "cheap midfielders" → `position eq MID, price lte 6.0`
3. **How to handle ambiguity** — "best players" → needs clarification: best by
   what metric? Total points? Form? Expected points?

**Kitchen example for the "recipes" subdomain, "read" step type:**

```
## Example: Recipe Search
User: "find me a quick chicken dinner"
Action: db_read on recipes
Filters: cook_time_minutes lte 30, tags contains "chicken", tags contains "dinner"
Note: Search by tags first, fall back to name ilike if no tag match

## Example: Recipe Detail
User: "show me recipe_1"
Action: db_read on recipes with id eq recipe_1
Includes: recipe_ingredients (nested)
Note: Always include ingredients for single-recipe reads
```

Good examples prevent the LLM from constructing bad queries. They're the most
impactful thing you can tune.

---

## What Your Domain Needs to Provide

### 0. System Identity

The overall personality of Alfred in your domain. This is NOT a per-subdomain
persona — it's the voice and identity that spans the entire conversation. It shapes
how Reply formats responses and how Think approaches planning.

**Kitchen example:**

```
You are Alfred, a helpful kitchen assistant.

You help home cooks manage recipes, plan meals, track ingredients,
and build shopping lists. You are practical, encouraging, and focused
on making cooking accessible.
```

Keep it to 1-2 paragraphs. This gets injected as the system prompt in the Reply
node, so it affects every response the user sees.

### 1. Entity Definitions

For EACH entity type users interact with, define:

| Field | What It Controls | Example |
|-------|-----------------|---------|
| `type_name` | Ref prefix — "player" produces `player_1`, `player_2` | 2-6 char noun (see note below) |
| `table` | Database table name | Must match exactly |
| `primary_field` | Default display field for labels | The most recognizable field (name, title) |
| `fk_fields` | Foreign key columns | Used for ref↔UUID translation and FK enrichment |
| `complexity` | Think node hint: `"high"` = stronger model | Set for entities requiring complex reasoning |
| `nested_relations` | Child tables to auto-include in reads | Only for tight parent-child relationships |
| `detail_tracking` | Track summary vs full reads | Useful for entities with expensive full reads |
| `label_fields` | Fields used to compute labels | Usually just the primary_field |

**`type_name` length matters.** Refs appear hundreds of times in prompts across every
turn. Kitchen uses: `recipe`, `inv`, `shop`, `meal`, `task`, `pref`, `ing`, `log`,
`flavor` — all 3-7 characters. `player_1` is good; `fantasy_player_1` wastes tokens
and clutters prompts. Aim for 2-6 characters when possible.

**Format your output as:**

```yaml
entities:
  players:
    type_name: "player"
    table: "players"
    primary_field: "web_name"
    fk_fields: ["team_id"]
    complexity: "high"
    label_fields: ["web_name"]  # Can be multiple: ["date", "meal_type"] → "2026-02-10 dinner"
    detail_tracking: true
    notes: "Core entity. Users search, compare, and analyze players constantly."

  teams:
    type_name: "team"
    table: "teams"
    primary_field: "name"
    notes: "Reference data. Users rarely interact directly — mostly accessed via player.team_id FK."
```

### 2. Subdomain Definitions

For EACH subdomain, define:

| Field | What It Controls |
|-------|-----------------|
| `name` | Identifier used in routing and prompts |
| `primary_table` | The main table for this subdomain |
| `related_tables` | Other tables accessible from this subdomain |
| `description` | Injected into Think prompt — helps LLM plan correctly |

**Plus these design details:**

| Detail | Why It Matters |
|--------|---------------|
| Common user queries | Helps us build quick-mode detection and subdomain routing |
| Typical CRUD patterns | What read/write/delete look like in this subdomain |
| Cross-subdomain access | Which other subdomains' tables this one needs |
| Aliases | Informal names users might use ("my team" → squad, "buy" → transfers) |

**Format your output as:**

```yaml
subdomains:
  squad:
    primary_table: "squad_selections"
    related_tables: ["players", "teams"]
    description: >
      Squad management. View current 15-player squad, check formation,
      team value, and bench order. Users say: 'show my team', 'who's
      in my squad', 'what's my team value', 'show my bench'.
    common_queries:
      quick_mode:
        - "show my squad"
        - "what's my team value?"
        - "who's my captain?"
      full_pipeline:
        - "suggest formation changes"
        - "who should I bench this week?"
    crud_patterns:
      read:
        - "Show current squad → read squad_selections filtered by current GW,
           FK-enrich player names and teams"
        - "Show squad value → read squad_selections with player prices"
      write:
        - "Set captain → update squad_selections captain field"
        - "Swap bench order → update squad_selections bench_order"
      delete:
        - "Rarely used directly — transfers handle adding/removing players"
    cross_subdomain_access: ["analysis"]
    aliases: ["my team", "team", "squad", "lineup", "formation"]
```

### 3. FK Enrichment Map

For each foreign key field across ALL tables:

```yaml
fk_enrichment:
  player_id:
    target_table: "players"
    name_column: "web_name"
    notes: "Most common FK. Appears in squad_selections, transfers, etc."
  team_id:
    target_table: "teams"
    name_column: "name"
```

### 4. User-Owned vs Reference Tables

```yaml
user_owned:
  - squad_selections    # Scoped to user_id automatically
  - transfers
  - watchlist

reference:
  - players             # Shared data, no user scoping
  - teams
  - gameweeks
  - fixtures
```

### 5. Personas (per subdomain)

Write as if briefing a human expert. Include:
- What they're an expert in
- What they prioritize
- What signals they watch for
- How they communicate (concise? detailed? analytical?)

### 6. Example Interactions (2-3 per subdomain)

Show realistic conversations with:
- What the user says
- What Alfred should do (which tables, what filters)
- What nuances exist (edge cases, common mistakes)
- What a good response includes

### 7. Schema

Table definitions with column names, types, and notes about what each column
represents. Include:
- Which columns are UUIDs (need ref translation)
- Which columns are enum-like (finite valid values)
- Which columns have semantic meaning that's not obvious from the name

### 8. Complex Workflows

Multi-step user goals that require planning:

```yaml
workflows:
  wildcard_planning:
    trigger: "plan my wildcard" / "help me wildcard" / "wildcard team"
    steps:
      - READ analysis: get top players per position by expected points
      - READ analysis: get fixture difficulty for next 5 GWs
      - ANALYZE: evaluate team combinations within 100.0 budget
      - GENERATE: produce suggested 15-player squad with formation
    notes: "This is the most complex workflow. Needs access to players,
            teams, fixtures, and current squad."
```

### 9. Generate Use Cases

If your domain has a "create content for approval" pattern:

```yaml
generate_patterns:
  squad_suggestion:
    trigger: "suggest a team" / "draft a wildcard"
    what_gets_generated: "Full 15-player squad with formation, captain, vice-captain"
    ref_pattern: "gen_squad_1"
    approval_flow: "User reviews → says 'save it' → writes to squad_selections"
```

### 10. Semantic Notes

Domain rules the LLM needs to know:

```yaml
semantic_notes:
  squad: "Squad has exactly 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD. Max 3 from any team."
  transfers: "Free transfers reset each GW. Extra transfers cost 4 points each."
  budget: "Total squad value starts at 100.0. Selling price is based on purchase price + 50% of profit."
```

### 11. Field Enums

Categorical fields with their valid values:

```yaml
field_enums:
  players:
    position: ["GKP", "DEF", "MID", "FWD"]
    status: ["available", "injured", "suspended", "doubtful"]
  squad_selections:
    is_captain: [true, false]
    is_vice_captain: [true, false]
    multiplier: [0, 1, 2, 3]  # 0=benched, 1=playing, 2=captain, 3=triple-captain
```

### 12. Empty Response Messages

What Alfred should say when a query returns no data. Every subdomain needs one.
Without these, Alfred gives generic "no results found" messages that feel broken.

```yaml
empty_responses:
  squad: "No squad selection found for this gameweek."
  transfers: "No transfers recorded this gameweek."
  analysis: "No player data found matching those criteria."
  gameweeks: "No gameweek data available."
```

Make them specific and actionable — "No transfers recorded this gameweek" is better
than "No data found."

---

## Kitchen Domain as Complete Reference

Here's the full kitchen domain structure so you can see a complete, working example:

### Kitchen Entities (10 types)

> Note: `primary_field` is the column used for display labels in prompts — NOT the
> database primary key. All tables use a UUID `id` column as their primary key
> (see Constraint #2).

| Entity | type_name | Table | Primary Field (display label) | FK Fields | Complexity | Nested |
|--------|-----------|-------|--------------|-----------|-----------|--------|
| Recipes | `recipe` | `recipes` | `name` | — | high | `recipe_ingredients` |
| Recipe Ingredients | `ri` | `recipe_ingredients` | `ingredient_id` | `recipe_id`, `ingredient_id` | — | — |
| Inventory | `inv` | `inventory` | `name` | `ingredient_id` | — | — |
| Shopping List | `shop` | `shopping_list` | `name` | `ingredient_id` | — | — |
| Meal Plans | `meal` | `meal_plans` | `date` | `recipe_id` | medium | — |
| Tasks | `task` | `tasks` | `title` | `recipe_id`, `meal_plan_id` | — | — |
| Preferences | `pref` | `preferences` | `name` | — | — | — |
| Ingredients | `ing` | `ingredients` | `name` | — | — | — |
| Cooking Log | `log` | `cooking_log` | `cooked_at` | `recipe_id` | — | — |
| Flavor Prefs | `flavor` | `flavor_preferences` | `name` | — | — | — |

### Kitchen Subdomains (7 groups)

| Subdomain | Primary Table | Related Tables | Description |
|-----------|--------------|----------------|-------------|
| recipes | `recipes` | `recipe_ingredients`, `ingredients` | Recipe search, browsing, details |
| inventory | `inventory` | `ingredients` | Pantry tracking |
| shopping | `shopping_list` | `ingredients` | Shopping list management |
| meal_plans | `meal_plans` | `recipes`, `tasks` | Weekly meal planning |
| tasks | `tasks` | `recipes`, `meal_plans` | Cooking tasks and prep |
| preferences | `preferences` | `flavor_preferences` | Dietary and flavor preferences |
| history | `cooking_log` | — | Cooking history and log |

### Kitchen FK Enrichment

```
recipe_id    → recipes.name        ("Butter Chicken")
ingredient_id → ingredients.name   ("Chicken Breast")
```

### Kitchen User-Owned Tables

`recipes`, `recipe_ingredients`, `inventory`, `shopping_list`, `meal_plans`,
`tasks`, `preferences`, `cooking_log`, `flavor_preferences`

### Kitchen Reference Tables

`ingredients` (shared ingredient database)

### Kitchen CRUD Middleware Behaviors

| Behavior | Subdomain | What It Does |
|----------|-----------|-------------|
| Semantic search | recipes | "Italian pasta" → pgvector similarity, not just name match |
| Auto-include | recipes | Single recipe read auto-includes recipe_ingredients |
| Fuzzy matching | inventory | "add chicken" → matches "Chicken Breast" in ingredients |
| Ingredient resolution | inventory, shopping | Plain text names resolved to ingredient IDs |

---

## Key Constraints

Things that constrain your design:

1. **Every user-owned table must have a `user_id` column** — CRUD auto-scopes by it
2. **Every table needs a UUID `id` primary key** — the ref system translates these
3. **FK fields must reference UUID primary keys** — for ref↔UUID translation
4. **The database must be Supabase (PostgreSQL + PostgREST)** — CRUD uses the
   PostgREST query builder API
5. **Row Level Security (RLS) must be enabled** — all data access goes through
   authenticated Supabase client, never raw DB access
6. **LLMs never see UUIDs** — the ref system handles all translation
7. **Generated content is never auto-saved** — users must explicitly approve
8. **Each step in a plan targets one subdomain** — tables needed across subdomains
   should be listed in each subdomain's table registry
9. **Subdomain descriptions are injected into Think prompts** — they should be
   concise (1-3 sentences) but specific enough to route correctly
10. **Persona text is injected into Act prompts** — it shapes every response in
    that subdomain

# Domain Questionnaire

> Structured interview for building a new Alfred domain.
> An LLM coder asks these questions to the domain expert, then maps answers to `DomainConfig` code.
> Ask in order — earlier answers inform later questions.

---

## Q1: What is your domain?

**Maps to:** `name`, `get_system_prompt()`

Answer in this format:

```
Domain name (1 word): ___
Alfred helps [who] with [what]. It can [key capabilities].
```

Example: *"Alfred helps home cooks manage recipes, plan meals, track ingredients, and build shopping lists."*

---

## Q2: What things do users interact with?

**Maps to:** `entities` (EntityDefinition), `get_fk_enrich_map()`, `get_uuid_fields()`

List every thing. For each one:

| Field | What to provide | Example |
|-------|-----------------|---------|
| Name (plural) | Database table name | `recipes` |
| Display name | The field a human would recognize it by | `name` → "Butter Chicken" |
| Ref prefix | 2-6 char shorthand for prompts | `recipe` → `recipe_1`, `recipe_2` |
| User-owned? | Does each user have their own, or is it shared? | user-owned / shared |
| FK columns | Foreign keys to other things (and UUID or integer?) | `recipe_id` (UUID), `team_id` (integer) |
| Parent-child? | Does it always appear nested under another thing? | `recipe_ingredients` nested under `recipes` |
| Complex? | Does reasoning about it need a stronger model? | high / medium / (blank) |

**Format your answer as a table.** One row per thing. This maps directly to `EntityDefinition` instances.

**Important:** Every table with FK columns needs an entry. There is no lightweight alternative — core requires entity definitions for ref↔UUID translation.

---

## Q3: What activities do users do?

**Maps to:** `subdomains` (SubdomainDefinition), `get_subdomain_registry()`, `get_subdomain_aliases()`

Group your things from Q2 into 3-7 user-facing activities. Each activity is a subdomain.

For each activity:

| Field | What to provide | Example |
|-------|-----------------|---------|
| Name | 1-word identifier | `squad` |
| Primary table | Main table for this activity | `squad_selections` |
| Other tables needed | Tables this activity reads/writes | `players`, `teams` |
| Description | 1-3 sentences for the LLM planner — what users do here, example phrases | "Squad management. View current squad, check formation, team value. Users say: 'show my team', 'who's my captain'." |
| Aliases | Informal names users might say | "my team", "lineup", "formation" |

**Design rule:** subdomains map to user intent, not database schema. "What is the user trying to do?" not "What table is this?"

---

## Q4: How should Alfred talk in each activity?

**Maps to:** `get_persona()`, `get_system_prompt()`

For each subdomain from Q3, describe the expert Alfred should be:

```
[subdomain]: You are a [role]. Focus on [priorities]. When [situation], [behavior].
```

Example: *"transfers: You are a transfer expert. Consider price changes, fixture difficulty over the next 5 gameweeks, and ownership percentage. Flag differential picks under 10% ownership."*

**Weak:** "You help with transfers."
**Strong:** "You are a transfer expert. Consider price changes and fixtures. Flag differentials under 10% ownership."

---

## Q5: Show 2-3 example conversations per activity

**Maps to:** `get_examples()`, `get_subdomain_examples()`

For each subdomain, provide realistic examples:

```
Subdomain: [name]
User: "[what they say]"
Action: [which CRUD operation] on [which table]
Filters: [field] [op] [value], ...
Notes: [edge cases, common mistakes, what a good response includes]
```

Example:
```
Subdomain: recipes
User: "find me a quick chicken dinner"
Action: db_read on recipes
Filters: cook_time_minutes lte 30, tags contains "chicken"
Notes: Search by tags first, fall back to name ilike if no tag match
```

These examples directly teach the LLM which tables to query and what filters to use. They are the highest-impact thing you can tune.

---

## Q6: What are the database tables and columns?

**Maps to:** `get_fallback_schemas()`, schema discovery choice

For each table from Q2, provide:

```
Table: [name]
Columns:
  - id (uuid, primary key)
  - user_id (uuid, auto-scoped for user-owned tables)
  - name (text, the recipe title)
  - position (text, one of: GKP/DEF/MID/FWD)
  - price (numeric, in millions, e.g., 12.5)
  - team_id (uuid FK → teams.id)
```

Flag three things per column:
1. Is it a UUID that needs ref translation?
2. Is it an enum with a fixed set of valid values?
3. Is its meaning non-obvious from the name?

**Schema discovery choice:** Does your Supabase instance have a `get_table_columns` RPC function? If yes, `get_fallback_schemas()` can return `{}`. If no (or you're unsure), provide the column definitions above — they become the fallback schemas. Without either, the LLM guesses column names and most queries fail.

---

## Q7: What domain rules must the LLM know?

**Maps to:** `get_semantic_notes()`, `get_field_enums()`

Two parts:

**A. Business rules** (one per subdomain):
```
squad: "Squad has exactly 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD. Max 3 from any team."
transfers: "Free transfers reset each GW. Extra transfers cost 4 points each."
```

**B. Valid values for categorical fields:**
```
players.position: GKP, DEF, MID, FWD
players.status: available, injured, suspended, doubtful
squad_selections.multiplier: 0, 1, 2, 3
```

All values must be strings (even numeric ones like "0", "1").

---

## Q8: What should Alfred say when queries return nothing?

**Maps to:** `get_empty_response()`

One message per subdomain. Make them specific and actionable.

```
squad: "No squad selection found for this gameweek."
transfers: "No transfers recorded this gameweek."
analysis: "No player data found matching those criteria."
```

**Weak:** "No data found."
**Strong:** "No transfers recorded this gameweek. Use 'buy [player]' to make a transfer."

---

## Q9: What complex workflows exist?

**Maps to:** Think prompt content, examples, GENERATE step patterns

Describe multi-step user goals:

```
Workflow: [name]
Trigger: "[what the user says]"
Steps:
  1. READ [subdomain]: [what to fetch]
  2. READ [subdomain]: [what else to fetch]
  3. ANALYZE: [what to reason about]
  4. GENERATE: [what to produce]
Notes: [what makes this complex]
```

If any workflow has a "create → review → save" pattern (user approves before database write), note which thing gets generated and what the `gen_*` ref looks like (e.g., `gen_recipe_1`).

---

## Q10: What's missing?

Ask the domain expert:

- Are there any edge cases or gotchas in your domain that a generic assistant would get wrong?
- Are there informal terms or slang users might use? (These become subdomain aliases.)
- Which queries are most common? (These become quick-mode candidates — single CRUD call, no planning needed.)
- Is there any data the LLM should never expose or modify? (These become guardrails.)

---

## After the Interview

The LLM coder now has everything needed to implement `DomainConfig`. Map answers to code:

| Question | DomainConfig method(s) |
|----------|----------------------|
| Q1 | `name`, `get_system_prompt()` |
| Q2 | `entities`, `get_fk_enrich_map()`, `get_uuid_fields()`, `get_user_owned_tables()` |
| Q3 | `subdomains`, `get_subdomain_registry()`, `get_subdomain_aliases()` |
| Q4 | `get_persona()` |
| Q5 | `get_examples()`, `get_subdomain_examples()` |
| Q6 | `get_fallback_schemas()` |
| Q7 | `get_semantic_notes()`, `get_field_enums()` |
| Q8 | `get_empty_response()` |
| Q9 | Think/Act prompt content, GENERATE patterns |
| Q10 | Guardrails, aliases, quick-mode routing |

Start with the scaffold in `docs/bridge/domain-scaffold/`. Copy it, rename `alfred_DOMAIN` to your domain name, and fill in the TODO placeholders using the answers above. See `domain-implementation-guide.md` for the full reference.

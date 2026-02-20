# New Domain Developer — Start Here

You're building a new domain for Alfred's orchestration engine (`alfredagain` on PyPI). This doc tells you what to read, in what order, and where to find it.

All docs live in this repo: **https://github.com/jv92admin/alfred-core**

---

## Phase 1: Understand What You're Building On

Read these first. They explain the engine your domain will plug into.

| # | Doc | What You'll Learn | Time |
|---|-----|-------------------|------|
| 1 | [overview.md](docs/architecture/overview.md) | What Alfred is, 5-stage pipeline (Understand → Think → Act → Reply → Summarize), execution patterns, what's deterministic vs LLM | 5 min |
| 2 | [pipeline-stages.md](docs/architecture/pipeline-stages.md) | What each node does, state flow between them, step types (read/write/analyze/generate), tool_call vs step_complete decisions | 15 min |
| 3 | [sessions-context-entities.md](docs/architecture/sessions-context-entities.md) | Entity refs (player_1, recipe_3), SessionIdRegistry, ref↔UUID translation, entity lifecycle, context curation, recency windows | 15 min |
| 4 | [core-domain-architecture.md](docs/architecture/core-domain-architecture.md) | DomainConfig protocol (23 abstract + 48 default methods), what each method group controls, supporting dataclasses | 10 min |

After these four, you understand the engine. You know what the pipeline does, how entities flow through it, and what your domain needs to provide.

## Phase 2: Design Your Domain

Before writing code, answer the design questions.

| # | Doc | What You'll Do | Time |
|---|-----|----------------|------|
| 5 | [domain-questionnaire.md](docs/bridge/domain-questionnaire.md) | 10 questions that extract your entities, subdomains, personas, schema, and edge cases. Fill this out before coding. | 30 min |
| 6 | [alfred-domain-design-guide.md](docs/bridge/alfred-domain-design-guide.md) | Deep-dive into each question with worked examples from Kitchen and FPL. Read alongside the questionnaire. | 20 min |

## Phase 3: Build It

Now implement, using the guide and scaffold.

| # | Doc | What You'll Do | Time |
|---|-----|----------------|------|
| 7 | [domain-implementation-guide.md](docs/architecture/domain-implementation-guide.md) | Step-by-step build guide. Entities, subdomains, DomainConfig (all 23 methods with examples), database adapter, middleware, prompts, testing, running, env vars. **This is the main reference.** | Reference |
| 8 | [domain-scaffold/](docs/bridge/domain-scaffold/) | Template project. Copy this directory, rename `alfred_DOMAIN` to `alfred_yourname`, fill in TODOs. Includes pyproject.toml, domain config with all contracts as comments, test file, runner script, .env.example. | Starting point |

## Phase 4: Go Deeper (As Needed)

Reference these when you hit specific questions during development.

| Doc | When You Need It |
|-----|-----------------|
| [prompt-assembly.md](docs/architecture/prompt-assembly.md) | Tuning prompts — understand how system/user prompts are assembled per node, injection variables, fallback chains, what your domain overrides replace |
| [crud-and-database.md](docs/architecture/crud-and-database.md) | Database integration — CRUD executor internals, ref translation, FK enrichment (two-phase), middleware hooks, Supabase expectations |
| [capabilities.md](docs/architecture/capabilities.md) | API contracts — all endpoints, request/response shapes, streaming events, mode system |
| [core-public-api.md](docs/architecture/core-public-api.md) | Import paths — every public function/class in `alfredagain`, organized by module |

---

## Quick Reference

**Install:** `pip install alfredagain`

**Import:** `import alfred` (then `from alfred.domain.base import DomainConfig, EntityDefinition, ...`)

**Required env var:** `OPENAI_API_KEY` in your `.env`

**Dev tip:** Set `ALFRED_USE_ADVANCED_MODELS=false` for cheap runs during development.

**Run a conversation:**
```python
import alfred_yourdomain  # triggers registration

from alfred.graph.workflow import run_alfred
from alfred.memory import initialize_conversation

conversation = initialize_conversation()
response, conversation = await run_alfred("hello", user_id="dev-123", conversation=conversation)
```

**Existing domains to study:**
- Kitchen (this repo's sibling): https://github.com/jv92admin/alfredagain — `src/alfred_kitchen/`
- FPL: https://github.com/jv92admin/fpltools — `src/alfred_fpl/`

**Core source:** https://github.com/jv92admin/alfred-core
**PyPI:** https://pypi.org/project/alfredagain/

# alfredagain

Domain-agnostic LLM orchestration engine built on LangGraph.

Alfred is a multi-agent assistant framework. You implement a `DomainConfig` to teach it your domain — entities, subdomains, prompts, database adapter — and Alfred handles the orchestration: routing, planning, CRUD execution, entity tracking, prompt assembly, and conversation memory.

## Install

```bash
pip install alfredagain
```

## Quick Start

```python
from alfred.domain.base import DomainConfig, EntityDefinition, SubdomainDefinition
from alfred.domain import register_domain

class MyDomain(DomainConfig):
    @property
    def name(self) -> str:
        return "mydomain"

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        # Define your entities...
        ...

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        # Define your subdomains...
        ...

    # Implement remaining abstract methods...

# Register and run
register_domain(MyDomain())

from alfred.graph.workflow import run_alfred
response, conversation = await run_alfred(
    user_message="Hello!",
    user_id="user_1",
)
```

## What Alfred Provides

- **Pipeline orchestration** — Understand → Think → Act → Reply, with LangGraph state management
- **Entity tracking** — SessionIdRegistry translates UUIDs to simple refs (recipe_1, item_2)
- **CRUD execution** — Schema-driven database operations with middleware hooks
- **Prompt assembly** — Domain-provided personas, examples, and context injection
- **Conversation memory** — Turn summarization, context windowing, session persistence
- **Model routing** — Complexity-based model selection (mini for simple, full for complex)
- **Streaming** — 11 typed events for real-time UI updates

## Architecture

Core is fully domain-agnostic. It never imports any domain package. Domains implement `DomainConfig` (74 methods — 23 abstract, 51 with defaults) and call `register_domain()`.

See `docs/architecture/` for detailed documentation:
- `overview.md` — Architecture index + pipeline diagram
- `domain-implementation-guide.md` — How to build a new domain
- `core-public-api.md` — Entry points, extension protocols

## Development

```bash
git clone https://github.com/jv92admin/alfred-core.git
cd alfred-core
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT

# Alfred DOMAIN

> TODO: One-line description of your domain.

Built on [alfredagain](https://pypi.org/project/alfredagain/) — Alfred's domain-agnostic orchestration engine.

## Quick Start

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e ".[dev]"

# Verify
pytest tests/ -v
```

## How This Works

1. `src/alfred_DOMAIN/__init__.py` registers your domain with Alfred's core engine on import
2. `src/alfred_DOMAIN/domain/__init__.py` implements `DomainConfig` — entities, subdomains, personas, examples
3. `src/alfred_DOMAIN/db/client.py` connects to your Supabase database
4. Core handles the pipeline: UNDERSTAND → THINK → ACT → REPLY → SUMMARIZE

## Key Files

| File | Purpose |
|------|---------|
| `domain/__init__.py` | DomainConfig — all 23 abstract methods |
| `domain/prompts/system.md` | Alfred's identity in your domain |
| `db/client.py` | Supabase client wrapper |
| `config.py` | Environment variables |

## Resources

- [Domain Questionnaire](https://github.com/jv92admin/alfred-core/blob/main/docs/bridge/domain-questionnaire.md) — structured interview for designing your domain
- [Domain Implementation Guide](https://github.com/jv92admin/alfred-core/blob/main/docs/architecture/domain-implementation-guide.md) — full reference with contracts
- [Domain Design Guide](https://github.com/jv92admin/alfred-core/blob/main/docs/bridge/alfred-domain-design-guide.md) — conceptual overview

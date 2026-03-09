---
name: doc-review
description: 'Post-release documentation review and propagation. Run after version bumps, bug fixes, or any code change touching architecture, DomainConfig, prompt templates, or pipeline behavior.'
---

# /doc-review

Post-release documentation review and propagation for alfred-core.

Run this after completing a version bump, bug fix, feature addition, or any code change that touches architecture, DomainConfig, prompt templates, or pipeline behavior.

---

## Tier 1: Core Git Docs (Source of Truth)

These are the authoritative architecture docs. Take time, spin up sub-agents for thorough cross-referencing.

**Files to check (in priority order):**

1. `docs/architecture/overview.md` — Architecture index, pipeline diagram, doc index table
2. `docs/architecture/core-domain-architecture.md` — Two-package split, DomainConfig protocol, method counts
3. `docs/architecture/core-public-api.md` — Entry points, extension protocols, capabilities
4. `docs/architecture/pipeline-stages.md` — Node flow, routing decisions, state shape
5. `docs/architecture/sessions-context-entities.md` — Entity lifecycle, SessionIdRegistry, ref patterns
6. `docs/architecture/crud-and-database.md` — CRUD execution, middleware, schema, filter operators
7. `docs/architecture/prompt-assembly.md` — Template loading, injection model, fallback chain
8. `docs/architecture/testing.md` — Test count, coverage map, mock strategies
9. `docs/architecture/capabilities.md` — User-facing capabilities matrix

**Prompt templates (check if behavior changed):**
- `src/alfred/prompts/templates/` — understand.md, think.md, router.md, reply.md, summarize.md
- `src/alfred/prompts/templates/act/` — base.md, crud.md, read.md, write.md, analyze.md, generate.md

**Review protocol:**
1. Read the latest CHANGELOG entry to understand what changed
2. For each changed src/ file, check if any Tier 1 doc references that code path
3. If a DomainConfig method was added/changed/removed, update `core-domain-architecture.md` method count
4. If pipeline routing changed, update `pipeline-stages.md`
5. If CRUD/filter behavior changed, update `crud-and-database.md`
6. If test count changed, update `testing.md`
7. If a new doc was added, update the index table in `overview.md`
8. Use sub-agents to grep for outdated references (old method names, removed features, wrong counts)

**Standard:** These docs must match the code exactly. Flag any discrepancy.

---

## Tier 2: Onboarding / Customer-Facing Docs

These are what domain implementers read. Review AFTER Tier 1 since Tier 1 changes inform what's stale here.

**Files to check:**

1. `docs/architecture/injection-map.md` — Every DomainConfig hook. If any hook was added/changed/removed, this MUST be updated.
2. `docs/architecture/domain-implementation-guide.md` — Step-by-step build guide. Check if new hooks need mention.
3. `docs/bridge/alfred-domain-design-guide.md` — Design-level guide with worked examples. Check examples still valid.
4. `docs/bridge/domain-questionnaire.md` — Domain interview questions. Rarely needs updating.
5. `docs/NEW-DOMAIN-START-HERE.md` — Reading path. Update if new docs were added.
6. `README.md` — Package overview, quick start, version badge.

**Review protocol:**
1. If a new DomainConfig method was added → update `injection-map.md` (add row to correct section)
2. If a DomainConfig method signature changed → update `injection-map.md` + `domain-implementation-guide.md`
3. If default prompt behavior changed → update `injection-map.md` (default column)
4. If a new doc was created → update `NEW-DOMAIN-START-HERE.md` reading path
5. Check `README.md` version references match `pyproject.toml`

**Standard:** A new domain developer should be able to follow these docs without hitting surprises.

---

## Tier 3: PyPI / Maintenance Artifacts

Easiest tier — mechanical updates.

**Files to check:**

1. `CHANGELOG.md` — Latest entry exists, follows Keep a Changelog format, version matches `pyproject.toml`
2. `pyproject.toml` — Version bumped, matches CHANGELOG
3. `docs/ROADMAP.md` — If a P1-P5 backlog item was completed, move it to "Completed" section
4. `roadmap/active/` — Any item folders that shipped in this release?
5. `roadmap/archive/` — Create `v{version}/` folder, move shipped item folders into it
6. `roadmap/BACKLOG.md` — If a backlog idea was addressed, move it to "Promoted" table

**Review protocol:**
1. Verify `pyproject.toml` version == latest CHANGELOG version == git tag (if tagged)
2. Verify CHANGELOG entry categorizes correctly (Fixed/Added/Changed/Removed)
3. Move shipped `roadmap/active/MMDD-slug/` folders to `roadmap/archive/v{version}/`
4. Fill in the "Shipped" section of each SUMMARY.md (version, commits, date)
5. If a `roadmap/BACKLOG.md` idea was addressed, update the Promoted table
6. If a `docs/ROADMAP.md` backlog item was addressed, update its status
7. Check that version was published to PyPI if applicable

**Standard:** Version numbers consistent everywhere. CHANGELOG accurate. Active items archived on release.

---

## Tier 4: Agent / Skill Configuration

**Files to check:**

1. `CLAUDE.md` — Key files table, documentation table, development commands, system boundaries
2. `.claude/settings.local.json` — Any permission or tool changes needed
3. `.claude/skills/` — Any skills need updating based on changes

**Review protocol:**
1. If a key file was added/renamed/removed → update `CLAUDE.md` Key Files table
2. If a new doc was added → update `CLAUDE.md` Documentation table
3. If development commands changed → update `CLAUDE.md` Development Commands
4. If system boundaries changed → update `CLAUDE.md` System Boundaries
5. If skill behavior references changed code → update the skill

**Standard:** CLAUDE.md must be the reliable quick-reference it claims to be.

---

## Output Format

After reviewing all tiers, output a report:

```
## Doc Review Report — v{version}

### Tier 1: Core Git Docs
- [ ] {doc}: {what was updated or "No changes needed"}
...

### Tier 2: Onboarding Docs
- [ ] {doc}: {what was updated or "No changes needed"}
...

### Tier 3: Maintenance
- [ ] CHANGELOG: {status}
- [ ] ROADMAP: {status}
- [ ] pyproject.toml: {status}

### Tier 4: Agent Config
- [ ] CLAUDE.md: {status}
- [ ] Skills: {status}

### Manual Review Flags
- {any docs that need human judgment, e.g. "injection-map.md examples may need domain-specific review"}
```

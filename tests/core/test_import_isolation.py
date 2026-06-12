"""
Seam-contract import-isolation guarantee (SEAM_CONTRACT.md §6 item 4).

Importing only `alfred.context` (the substrate home module) must never import
langgraph or instructor — nor core's own LLM/pipeline modules. Each test runs
in a fresh subprocess so this suite's own imports can't mask a violation, and
names the offending modules on failure.
"""

import json
import subprocess
import sys

# The seam contract names langgraph/instructor; alfred.graph / alfred.llm are
# the in-repo modules that import them — forbidding those too catches a
# violation even if the heavy dependency happens to be uninstalled.
FORBIDDEN_PREFIXES = (
    "langgraph",
    "instructor",
    "alfred.graph",
    "alfred.llm",
)


def _forbidden_modules_after_importing(module: str) -> list[str]:
    """Import `module` in a fresh interpreter; return forbidden sys.modules entries."""
    code = (
        "import json, sys\n"
        f"import {module}\n"
        f"offenders = sorted(m for m in sys.modules if m.startswith({FORBIDDEN_PREFIXES!r}))\n"
        "print(json.dumps(offenders))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`import {module}` failed in a fresh interpreter:\n{result.stderr}"
    )
    offenders: list[str] = json.loads(result.stdout)
    return offenders


def test_alfred_context_never_imports_llm_stack():
    """The guarantee ledge builds against: `import alfred.context` stays C0-clean."""
    offenders = _forbidden_modules_after_importing("alfred.context")
    assert offenders == [], (
        "importing alfred.context pulled in forbidden modules "
        f"(seam contract §6 item 4 violated): {offenders}"
    )


def test_alfred_domain_never_imports_llm_stack():
    """DomainContext's canonical home (alfred.domain) carries the same guarantee."""
    offenders = _forbidden_modules_after_importing("alfred.domain")
    assert offenders == [], f"importing alfred.domain pulled in forbidden modules: {offenders}"


# ---------------------------------------------------------------------------
# A3 (0612-assembly-entrypoints) — E5: the assembly chain is state-free.
# Beyond the LLM stack, the assembly module must never import session
# machinery: the S1 registry composes into the identity-policy seat from
# OUTSIDE (the golden fixture imports it; the module must not).
# ---------------------------------------------------------------------------

ASSEMBLY_FORBIDDEN_PREFIXES = FORBIDDEN_PREFIXES + ("alfred.core.id_registry",)


def test_assembly_module_never_imports_llm_or_session_machinery():
    """E2/E5: alfred.context.assembly imports no LLM stack and no session registry."""
    code = (
        "import json, sys\n"
        "import alfred.context.assembly\n"
        f"offenders = sorted(m for m in sys.modules if m.startswith({ASSEMBLY_FORBIDDEN_PREFIXES!r}))\n"
        "print(json.dumps(offenders))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"`import alfred.context.assembly` failed in a fresh interpreter:\n{result.stderr}"
    )
    offenders = json.loads(result.stdout)
    assert offenders == [], (
        f"alfred.context.assembly pulled in forbidden modules (E5 violated): {offenders}"
    )


def test_assembly_module_source_has_no_global_state_access():
    """E5 source-level guards: no module-global domain, no ContextVar, no AlfredState.

    The no-silent-global-fallback guarantee (GROUNDING P1) is enforced
    mechanically, not by convention: the adapter may only arrive via
    ctx.get_db_adapter(). AST-based so docstrings/comments may *mention* the
    forbidden names (the module documents its own guarantees) — only actual
    code identifiers fail.
    """
    import ast
    import inspect

    import alfred.context.assembly as assembly

    forbidden = {"get_current_domain", "ContextVar", "AlfredState", "contextvars"}
    identifiers: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(assembly))):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.Import):
            identifiers.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            identifiers.add((node.module or "").split(".")[0])
            identifiers.update(alias.name for alias in node.names)

    offenders = identifiers & forbidden
    assert offenders == set(), (
        f"alfred.context.assembly uses {sorted(offenders)} — the assembly "
        f"chain must be state-free (E2/E5)."
    )

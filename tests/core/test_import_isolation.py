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

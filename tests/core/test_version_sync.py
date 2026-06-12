"""Version-sync guard.

``alfred.__version__`` is a recorded literal duplicating the authoritative
version in ``pyproject.toml`` — it sat at "2.4.0" through three minor releases
because nothing compared the two (PITFALLS: ``recorded-number-drift``). This
pins it to the installed package metadata so the drift is structurally
impossible to ship: the suite fails the moment the two disagree.

A stale editable install (metadata frozen at ``pip install -e`` time) also
fails this test — that's the guard working; re-run ``pip install -e ".[dev]"``
after a version bump.
"""

from importlib import metadata

import alfred


def test_version_matches_package_metadata():
    assert alfred.__version__ == metadata.version("alfredagain"), (
        f"alfred.__version__ ({alfred.__version__!r}) != installed package "
        f"metadata ({metadata.version('alfredagain')!r}) — sync "
        "src/alfred/__init__.py with pyproject.toml (and reinstall editable)."
    )

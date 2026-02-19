"""Test configuration — registers the domain before any tests run."""

import os

# Required env vars for core
os.environ.setdefault("ALFRED_ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Register the domain — importing the package triggers _register()
import alfred_DOMAIN  # noqa: F401  # TODO: rename

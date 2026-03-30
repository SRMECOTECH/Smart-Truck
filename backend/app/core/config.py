"""
Backend config — re-exports from centralized config/ package.
All services share the same Settings instance.
"""

from config.settings import settings  # noqa: F401

# Backward compat: anything importing `from backend.app.core.config import settings` still works.

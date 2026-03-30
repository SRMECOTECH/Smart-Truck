"""
Backend database — re-exports from centralized config/ package.
All services share the same connection helpers.
"""

from config.database import (  # noqa: F401
    get_connection,
    get_db,
    db_session,
    get_conn,
    init_database,
)

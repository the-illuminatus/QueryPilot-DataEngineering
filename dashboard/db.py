"""Read-only PostgreSQL connection for the dashboard.

Reuses src.warehouse.db.get_engine() -- which reads config.settings.postgres
and never hardcodes credentials -- rather than building a second, parallel
connection path. Two things are added here: Streamlit-level caching, so
the dashboard shares one connection pool across the whole session instead
of opening a new one per widget/rerun; and a DB-session-level read-only
guarantee (SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY on every
connection pulled from the pool), so even a coding mistake elsewhere in
the dashboard can never write to the warehouse.
"""

from typing import Optional

import streamlit as st
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.warehouse.db import get_engine as _get_warehouse_engine


def build_readonly_engine(database: Optional[str] = None) -> Engine:
    engine = _get_warehouse_engine(database=database)

    @event.listens_for(engine, "connect")
    def _enforce_read_only(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        cursor.close()
        # SET SESSION CHARACTERISTICS only affects transactions started
        # *after* it takes effect -- not the implicit one it runs inside.
        # Commit here so the next transaction (the caller's actual query)
        # starts fresh and picks up the read-only default.
        dbapi_connection.commit()

    return engine


@st.cache_resource
def get_engine() -> Engine:
    return build_readonly_engine()

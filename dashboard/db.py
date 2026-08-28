"""Read-only PostgreSQL connection for the dashboard.

Reuses src.warehouse.db.get_readonly_engine() -- which reads
config.settings.postgres and never hardcodes credentials -- rather than
building a second, parallel connection path. That shared function is
also what gives every connection its DB-session-level read-only
guarantee (SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY), so
even a coding mistake elsewhere in the dashboard can never write to the
warehouse. What's added here is Streamlit-specific: caching, so the
dashboard shares one connection pool across the whole session instead
of opening a new one per widget/rerun.

`build_readonly_engine` is kept as this module's public name (existing
callers/tests use it) but is now a thin wrapper -- the read-only engine
itself is built once, centrally, in src/warehouse/db.py so any
read-only consumer (this dashboard, or src/nl2sql's execution layer)
builds on the exact same guarantee instead of each layer
re-implementing it.
"""

import streamlit as st
from sqlalchemy.engine import Engine

from src.warehouse.db import get_readonly_engine as build_readonly_engine

__all__ = ["build_readonly_engine", "get_engine"]


@st.cache_resource
def get_engine() -> Engine:
    return build_readonly_engine()

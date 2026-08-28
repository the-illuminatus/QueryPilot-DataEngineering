"""Database engine creation for the warehouse loader.

Reads connection settings from config.settings.postgres -- never hardcodes
credentials. `get_engine()` builds a fresh SQLAlchemy engine per call so
tests can point it at an isolated database (typically a throwaway one on
the same server) without touching global configuration.
"""

from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from config import settings


def get_engine(database: Optional[str] = None) -> Engine:
    if database is None:
        url = settings.postgres.sqlalchemy_url
    else:
        base = settings.postgres
        url = (
            f"postgresql+psycopg2://{quote_plus(base.user)}:{quote_plus(base.password)}"
            f"@{base.host}:{base.port}/{database}"
        )
    return create_engine(url, future=True)


def get_readonly_engine(database: Optional[str] = None) -> Engine:
    """A warehouse engine with a DB-session-level read-only guarantee:
    every connection pulled from the pool runs
    `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` before it's
    handed out, so even a coding mistake in a caller can never write to
    the warehouse through it. Lives here (rather than only in
    dashboard/db.py, the original caller) so any read-only consumer --
    the dashboard, or src/nl2sql's execution layer -- can build on the
    same guarantee via this one shared connection path, instead of
    each layer re-implementing it against get_engine() independently.
    """
    engine = get_engine(database=database)

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

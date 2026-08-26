"""Database engine creation for the warehouse loader.

Reads connection settings from config.settings.postgres -- never hardcodes
credentials. `get_engine()` builds a fresh SQLAlchemy engine per call so
tests can point it at an isolated database (typically a throwaway one on
the same server) without touching global configuration.
"""

from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine
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

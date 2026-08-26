"""Shared pytest fixtures for tests that need a real PostgreSQL database.

Used by test_warehouse.py and test_dashboard.py. A fresh, uniquely-named
throwaway database is created per test *module* that requests `engine`
and dropped afterward -- the user's normal POSTGRES_DB is never touched.
If no server is reachable, or the configured user cannot create a
database, the requesting module is skipped with a message explaining
exactly what's required, rather than failing or silently passing.

Required setup to run these tests:
  - A running PostgreSQL server reachable using the POSTGRES_HOST/PORT/
    USER/PASSWORD in `.env` (see `.env.example`).
  - That user must be able to CREATE DATABASE / DROP DATABASE (a local
    superuser, e.g. the default `postgres` role, satisfies this).
"""

import uuid
from urllib.parse import quote_plus

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from config import settings
from src.ingestion.schemas import EXPECTED_COLUMNS
from src.transformation.writer import curated_entity_path


def _admin_url() -> str:
    base = settings.postgres
    return (
        f"postgresql+psycopg2://{quote_plus(base.user)}:{quote_plus(base.password)}"
        f"@{base.host}:{base.port}/postgres"
    )


def _test_db_url(test_db_name: str) -> str:
    base = settings.postgres
    return (
        f"postgresql+psycopg2://{quote_plus(base.user)}:{quote_plus(base.password)}"
        f"@{base.host}:{base.port}/{test_db_name}"
    )


@pytest.fixture(scope="module")
def engine():
    test_db_name = f"dataeng_test_{uuid.uuid4().hex[:8]}"

    try:
        admin_engine = create_engine(_admin_url(), future=True, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    except OperationalError as exc:
        pytest.skip(
            "No reachable PostgreSQL server for these tests. Set "
            "POSTGRES_HOST/PORT/USER/PASSWORD in .env to point at a running "
            f"PostgreSQL instance. Underlying error: {exc}"
        )
    except ProgrammingError as exc:
        pytest.skip(
            "Connected to PostgreSQL, but the configured user could not "
            "CREATE DATABASE for an isolated test database. Use a role with "
            f"that privilege (e.g. a local superuser). Underlying error: {exc}"
        )

    test_engine = create_engine(_test_db_url(test_db_name), future=True)
    yield test_engine
    test_engine.dispose()

    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :db AND pid <> pg_backend_pid()"
            ),
            {"db": test_db_name},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db_name}"'))
    admin_engine.dispose()


def _df(rows, entity):
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS[entity])


def _write_curated_batch(batch_id, entity_frames, monkeypatch, tmp_path):
    curated_dir = tmp_path / "data" / "curated"
    monkeypatch.setattr(settings, "DATA_CURATED_DIR", curated_dir)
    for entity, df in entity_frames.items():
        path = curated_entity_path(entity, batch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
    return curated_dir

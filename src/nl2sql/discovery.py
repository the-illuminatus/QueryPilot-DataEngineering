"""PostgreSQL schema/catalog discovery for the NL2SQL layer.

Uses SQLAlchemy's reflection API (`sqlalchemy.inspect`) against the
warehouse database -- no raw information_schema SQL of our own to
maintain, and no new dependency (SQLAlchemy is already required). This
reuses `src.warehouse.db.get_engine()` for the connection, the same
connection path the warehouse loader and dashboard both use, rather than
building a second parallel configuration path.

Discovery is read-only (schema reflection only issues SELECTs against
PostgreSQL's system catalogs) and safe to run at any time, including
against the live warehouse.
"""

from typing import Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.warehouse.db import get_engine

from .descriptions import TABLE_DESCRIPTIONS
from .models import ColumnInfo, ForeignKeyInfo, SchemaInfo, TableInfo

PUBLIC_SCHEMA = "public"


def discover_schema(engine: Optional[Engine] = None) -> SchemaInfo:
    """Reflects every table in the `public` schema of the warehouse
    database into a `SchemaInfo`. Table order is alphabetical so the
    result -- and anything built from it, like prompt context -- is
    deterministic across runs."""
    engine = engine or get_engine()
    inspector = inspect(engine)

    tables = []
    for table_name in sorted(inspector.get_table_names(schema=PUBLIC_SCHEMA)):
        tables.append(_discover_table(inspector, table_name))
    return SchemaInfo(tables=tuple(tables))


def _discover_table(inspector, table_name: str) -> TableInfo:
    pk_constraint = inspector.get_pk_constraint(table_name, schema=PUBLIC_SCHEMA)
    pk_columns = tuple(pk_constraint.get("constrained_columns") or ())
    pk_set = set(pk_columns)

    columns = tuple(
        ColumnInfo(
            name=col["name"],
            data_type=str(col["type"]),
            nullable=bool(col["nullable"]),
            is_primary_key=col["name"] in pk_set,
            default=str(col["default"]) if col.get("default") is not None else None,
        )
        for col in inspector.get_columns(table_name, schema=PUBLIC_SCHEMA)
    )

    foreign_keys = tuple(
        ForeignKeyInfo(
            column=local_col,
            references_table=fk["referred_table"],
            references_column=referred_col,
        )
        for fk in inspector.get_foreign_keys(table_name, schema=PUBLIC_SCHEMA)
        for local_col, referred_col in zip(fk["constrained_columns"], fk["referred_columns"])
    )

    check_constraints = tuple(
        sorted(
            c["sqltext"]
            for c in inspector.get_check_constraints(table_name, schema=PUBLIC_SCHEMA)
            if c.get("sqltext")
        )
    )

    return TableInfo(
        name=table_name,
        columns=columns,
        primary_key=pk_columns,
        foreign_keys=foreign_keys,
        check_constraints=check_constraints,
        description=TABLE_DESCRIPTIONS.get(table_name),
    )

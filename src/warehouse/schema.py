"""Applies the warehouse DDL (sql/ddl/*.sql) idempotently.

Every statement in sql/ddl/ uses IF NOT EXISTS, so applying the schema is
always safe to repeat -- it never drops or alters existing objects. Files
are applied in filename order, which is also dependency order (the
numeric prefixes exist specifically for this).
"""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

DDL_DIR = Path(__file__).resolve().parent.parent.parent / "sql" / "ddl"


def _strip_line_comments(sql: str) -> str:
    # A "--" comment can itself contain a semicolon (plain English prose
    # does), which would otherwise fool a naive split(";") into treating
    # the comment as its own (empty) statement. Comments carry no SQL
    # meaning, so drop them before splitting.
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def apply_schema(engine: Engine) -> None:
    ddl_files = sorted(DDL_DIR.glob("*.sql"))
    with engine.begin() as conn:
        for path in ddl_files:
            sql = _strip_line_comments(path.read_text())
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for statement in statements:
                conn.execute(text(statement))

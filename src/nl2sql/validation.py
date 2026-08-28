"""SQL validation / safety gate for LLM-generated candidate SQL.

Statically analyzes a candidate SQL string (typically
`SQLGenerationResult.sql` from generation.py) using sqlglot's
PostgreSQL-dialect parser and accepts only a single, read-only
SELECT-family statement. This module never executes SQL and never
connects to PostgreSQL -- see the pipeline docstring in
src/nl2sql/__init__.py for where this sits relative to generation and
(future) execution.

Security note: the generation prompt asks the model for read-only SQL,
but a prompt is not enforcement -- this module is the actual boundary.
Every check here works off the parsed AST, not surface keywords or the
model's stated intent, which is what lets it catch things a keyword
blocklist would miss:
  - DML hidden inside a CTE, e.g.
    `WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x`
    (the top-level statement is a Select; only a full-tree walk finds
    the Delete nested inside it)
  - `SELECT ... INTO new_table FROM ...` (a SELECT that creates a table)
  - a semicolon inside a string literal being mistaken for a statement
    separator (sqlglot's parser, unlike a naive `sql.split(";")`,
    tracks quoting)
  - administrative/unsupported statements (VACUUM, EXPLAIN, GRANT, ...)
    that sqlglot can't map to a specific expression type and falls back
    to an opaque `Command` node -- rejected by default since it wasn't
    positively identified as a read query, not assumed safe because it
    wasn't positively identified as anything else
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from .models import SchemaInfo

DIALECT = "postgres"

# Node types anywhere in the parsed tree that mean the statement is not
# a pure read query, regardless of where they appear (top level or
# nested inside a CTE). exp.Command is sqlglot's catch-all for anything
# it could not parse into a specific statement type -- deny by default,
# not allow by default.
_UNSAFE_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Command,
    exp.Merge,
    exp.Grant,
    exp.Set,
    exp.Use,
    exp.Copy,
)

# Root statement types that represent a read query. A `WITH ... SELECT`
# or `WITH ... SELECT UNION SELECT` still roots at Select/Union -- the
# With node is attached elsewhere in the tree, not a distinct root type.
_READ_ROOT_TYPES = (exp.Select, exp.Union, exp.Except, exp.Intersect)

# PostgreSQL functions that are administrative/side-effecting rather
# than read-only, and so must never be reachable through generated SQL
# even though they're syntactically callable from inside a SELECT.
# Defense in depth on top of the node-type walk above, which does not
# by itself distinguish a function call from any other expression.
_UNSAFE_FUNCTION_NAMES = frozenset(
    {
        "pg_sleep", "pg_sleep_for", "pg_sleep_until",
        "pg_terminate_backend", "pg_cancel_backend",
        "pg_reload_conf", "pg_rotate_logfile",
        "lo_import", "lo_export",
        "dblink", "dblink_connect", "dblink_exec",
        "pg_read_file", "pg_read_binary_file", "pg_ls_dir",
        "set_config", "pg_switch_wal", "pg_create_restore_point",
    }
)


@dataclass(frozen=True)
class SQLValidationResult:
    is_valid: bool
    normalized_sql: Optional[str] = None
    errors: Tuple[str, ...] = field(default_factory=tuple)
    referenced_tables: Tuple[str, ...] = field(default_factory=tuple)


def _invalid(errors: List[str]) -> SQLValidationResult:
    return SQLValidationResult(is_valid=False, normalized_sql=None, errors=tuple(errors), referenced_tables=())


def _cte_aliases(root: exp.Expression) -> set:
    with_clause = root.find(exp.With)
    if with_clause is None:
        return set()
    return {cte.alias_or_name for cte in with_clause.expressions}


def validate_sql(sql: Optional[str], schema: Optional[SchemaInfo] = None) -> SQLValidationResult:
    """Statically validates `sql` as safe to later execute read-only
    against the warehouse. Never executes anything and never opens a
    database connection. If `schema` is given, every referenced table
    is also checked against it -- a table the schema doesn't know about
    is a validation error, catching a hallucinated table before it ever
    reaches PostgreSQL."""
    if sql is None or not sql.strip():
        return _invalid(["SQL is empty."])

    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as exc:
        return _invalid([f"SQL failed to parse: {exc}"])

    if len(statements) == 0:
        return _invalid(["SQL contains no executable statement (empty or comment-only)."])
    if len(statements) > 1:
        return _invalid([f"Only a single statement is allowed; found {len(statements)}."])

    root = statements[0]

    if not isinstance(root, _READ_ROOT_TYPES):
        return _invalid([f"Only read (SELECT) statements are allowed; found '{root.key}'."])

    errors: List[str] = []

    if root.args.get("into") is not None:
        errors.append("SELECT INTO is not allowed (it creates a table).")

    unsafe_nodes = sorted({type(node).__name__ for node in root.walk() if isinstance(node, _UNSAFE_NODE_TYPES)})
    if unsafe_nodes:
        errors.append(f"Statement contains disallowed operation(s): {', '.join(unsafe_nodes)}.")

    unsafe_funcs = sorted(
        {
            node.this.lower()
            for node in root.find_all(exp.Anonymous)
            if isinstance(node.this, str) and node.this.lower() in _UNSAFE_FUNCTION_NAMES
        }
    )
    if unsafe_funcs:
        errors.append(f"Statement calls disallowed function(s): {', '.join(unsafe_funcs)}.")

    cte_aliases = _cte_aliases(root)
    referenced_tables = tuple(sorted({table.name for table in root.find_all(exp.Table) if table.name not in cte_aliases}))

    if schema is not None:
        unknown_tables = sorted(set(referenced_tables) - set(schema.table_names))
        if unknown_tables:
            errors.append(f"References table(s) not in the warehouse schema: {', '.join(unknown_tables)}.")

    if errors:
        return _invalid(errors)

    normalized_sql = root.sql(dialect=DIALECT) + ";"
    return SQLValidationResult(
        is_valid=True,
        normalized_sql=normalized_sql,
        errors=(),
        referenced_tables=referenced_tables,
    )

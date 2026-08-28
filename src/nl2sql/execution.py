"""Bounded, read-only SQL execution for validated NL2SQL candidates.

This is the last stage of Discovery -> Context -> Generation ->
Validation -> Execution. It runs exactly the SQL that already passed
Phase 7C validation (validation.py) against the warehouse -- never SQL
text supplied any other way -- over a connection that carries its own,
independent read-only guarantee, with a server-side statement timeout
and a client-side row cap. Nothing here is a dashboard/UI concern; see
src/nl2sql/__init__.py for where this sits in the overall pipeline.

Defense in depth, deliberately layered rather than relying on any one
check:
  - Static validation (already done, by the time SQL reaches here):
    validation.py's AST walk rejects DML/DDL, including DML smuggled
    inside a CTE.
  - Type-level trust boundary: execute_sql() only accepts a
    SQLValidationResult, not a raw string, and refuses to run anything
    unless `is_valid` is True -- so calling this with unvalidated SQL
    text is not just discouraged, it does not type-check.
  - DB-session-level read-only enforcement, independent of validation.py
    entirely: the engine (reused from src.warehouse.db.get_readonly_engine,
    the same one the dashboard already uses) runs
    `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` on every
    connection. Even if a query somehow slipped past validation, the
    database session itself would still refuse to write.
  - Bounded resource usage: a Postgres-side `SET LOCAL statement_timeout`
    caps how long a query may run, and results are streamed and capped
    client-side at `max_rows` (via `fetchmany`, not a `LIMIT` clause
    spliced into the already-validated SQL -- executing the exact text
    that was validated matters more than a marginally more efficient
    query).
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.warehouse.db import get_readonly_engine

from .validation import SQLValidationResult

DEFAULT_MAX_ROWS = 1000
DEFAULT_TIMEOUT_SECONDS = 30.0


class SQLExecutionError(ValueError):
    """Raised for caller misuse of execute_sql() itself (an unvalidated
    or invalid SQLValidationResult, a nonsensical max_rows/timeout) --
    never for an ordinary runtime failure while querying the warehouse
    (a Postgres error, a timeout, a connection drop). Those are
    legitimate, expected outcomes of a bounded executor and are
    reported via SQLExecutionResult.success / .error instead, so a
    caller doesn't need a try/except around every query."""


@dataclass(frozen=True)
class SQLExecutionResult:
    success: bool
    columns: Tuple[str, ...] = field(default_factory=tuple)
    rows: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    row_count: int = 0
    truncated: bool = False
    error: Optional[str] = None
    elapsed_seconds: float = 0.0


def execute_sql(
    validation_result: SQLValidationResult,
    engine: Optional[Engine] = None,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> SQLExecutionResult:
    """Executes `validation_result.normalized_sql` -- and only that --
    read-only against the warehouse. Raises SQLExecutionError if
    `validation_result` isn't a passed validation (caller misuse);
    returns a `success=False` result for any failure that happens while
    actually talking to Postgres (bad SQL at runtime, statement-timeout
    cancellation, connection failure, etc.)."""
    if not isinstance(validation_result, SQLValidationResult):
        raise SQLExecutionError(
            "execute_sql requires a SQLValidationResult produced by "
            f"validate_sql(); got {type(validation_result).__name__}."
        )
    if not validation_result.is_valid or not validation_result.normalized_sql:
        raise SQLExecutionError(
            "Refusing to execute: validation_result.is_valid is False. "
            f"Validation errors: {'; '.join(validation_result.errors) or '(none recorded)'}"
        )
    if not isinstance(max_rows, int) or isinstance(max_rows, bool) or max_rows <= 0:
        raise SQLExecutionError(f"max_rows must be a positive integer; got {max_rows!r}.")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
        raise SQLExecutionError(f"timeout_seconds must be a positive number; got {timeout_seconds!r}.")

    engine = engine or get_readonly_engine()
    sql = validation_result.normalized_sql
    timeout_ms = int(timeout_seconds * 1000)

    start = time.monotonic()
    try:
        with engine.connect() as conn:
            with conn.begin():
                # Scoped to this transaction only (SET LOCAL) -- never
                # leaks a custom timeout onto a connection reused for a
                # later, unrelated query out of this same pool. The
                # value is our own int * 1000, never caller-supplied
                # SQL text, so splicing it into the statement is safe.
                # Plain execute (no stream_results yet): a server-side
                # cursor can only be declared for a row-returning
                # statement, and SET is not one.
                conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                # stream_results is applied to this one call only, so
                # rows are pulled incrementally rather than buffered
                # in full before max_rows caps what we keep.
                result = conn.execution_options(stream_results=True).execute(text(sql))
                columns = tuple(result.keys())
                fetched = result.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = tuple(dict(zip(columns, row)) for row in fetched[:max_rows])
        return SQLExecutionResult(
            success=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            error=None,
            elapsed_seconds=round(time.monotonic() - start, 3),
        )
    except SQLAlchemyError as exc:
        return SQLExecutionResult(
            success=False,
            error=str(exc),
            elapsed_seconds=round(time.monotonic() - start, 3),
        )

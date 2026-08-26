"""Post-load reconciliation checks against the warehouse.

Every check here compares the warehouse's actual state to what was
expected from the curated input for one specific batch: row counts,
primary-key uniqueness, foreign-key integrity, unexpected nulls, and
monetary totals. The schema's own constraints already enforce PK/FK/NOT
NULL at the database level, so a failure here would mean something is
badly wrong with the load itself (or the constraints were bypassed) --
it is not a data-quality condition, that was already handled in Phase 3.
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection


class WarehouseQualityError(Exception):
    """Raised when a post-load reconciliation check fails."""


def count_rows_for_batch(conn: Connection, table: str, batch_id: str) -> int:
    result = conn.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).scalar()
    return int(result)


def verify_row_counts(conn: Connection, entity_counts: dict, batch_id: str) -> dict:
    results = {}
    for entity, expected_count in entity_counts.items():
        actual_count = count_rows_for_batch(conn, entity, batch_id)
        results[entity] = {"expected": expected_count, "actual": actual_count}
        if actual_count != expected_count:
            raise WarehouseQualityError(
                f"{entity}: expected {expected_count} rows tagged batch_id={batch_id}, "
                f"warehouse has {actual_count}"
            )
    return results


def verify_primary_key_uniqueness(conn: Connection, table: str, pk_column: str) -> None:
    duplicates = conn.execute(
        text(f"SELECT {pk_column} FROM {table} GROUP BY {pk_column} HAVING COUNT(*) > 1")
    ).fetchall()
    if duplicates:
        raise WarehouseQualityError(f"{table}: {len(duplicates)} duplicate {pk_column} value(s) found")


def verify_no_orphan_foreign_keys(
    conn: Connection, child_table: str, fk_column: str, parent_table: str, parent_pk: str
) -> None:
    orphan_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*) FROM {child_table} c
            LEFT JOIN {parent_table} p ON c.{fk_column} = p.{parent_pk}
            WHERE p.{parent_pk} IS NULL
            """
        )
    ).scalar()
    if orphan_count:
        raise WarehouseQualityError(
            f"{child_table}.{fk_column}: {orphan_count} orphaned reference(s) to {parent_table}"
        )


def verify_no_unexpected_nulls(conn: Connection, table: str, columns: list) -> None:
    for column in columns:
        null_count = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL")).scalar()
        if null_count:
            raise WarehouseQualityError(f"{table}.{column}: {null_count} unexpected NULL(s)")


def verify_monetary_total(
    conn: Connection, table: str, column: str, batch_id: str, expected_total: float
) -> dict:
    actual_total = conn.execute(
        text(f"SELECT COALESCE(SUM({column}), 0) FROM {table} WHERE batch_id = :batch_id"),
        {"batch_id": batch_id},
    ).scalar()
    actual_total = float(actual_total)
    if round(abs(actual_total - expected_total), 2) > 0.01:
        raise WarehouseQualityError(
            f"{table}.{column}: warehouse total {actual_total} != curated total {expected_total} "
            f"for batch_id={batch_id}"
        )
    return {"expected": round(expected_total, 2), "actual": round(actual_total, 2)}

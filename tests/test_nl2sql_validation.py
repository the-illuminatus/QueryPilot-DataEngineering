"""Tests for the SQL validation / safety gate (src/nl2sql/validation.py).

Pure, offline, deterministic -- no database connection and no LLM call.
Exercises the validator directly against hand-written SQL strings,
including adversarial ones designed to slip past a naive keyword
blocklist (DML hidden in a CTE, a semicolon inside a string literal).
"""

import pytest

from src.nl2sql.models import ColumnInfo, SchemaInfo, TableInfo
from src.nl2sql.validation import SQLValidationResult, validate_sql


def _table(name: str) -> TableInfo:
    return TableInfo(
        name=name,
        columns=(ColumnInfo(name="id", data_type="VARCHAR(20)", nullable=False, is_primary_key=True),),
        primary_key=("id",),
    )


WAREHOUSE_SCHEMA = SchemaInfo(
    tables=(_table("orders"), _table("customers"), _table("products"))
)


# ---------------------------------------------------------------------------
# 1. Empty SQL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sql", ["", "   ", "\n\t  \n", None, "-- just a comment\n"])
def test_rejects_empty_or_unusable_sql(sql):
    result = validate_sql(sql)
    assert result.is_valid is False
    assert result.normalized_sql is None
    assert result.errors


# ---------------------------------------------------------------------------
# 2. Single statement only
# ---------------------------------------------------------------------------


def test_accepts_a_single_select_statement():
    result = validate_sql("SELECT * FROM orders")
    assert result.is_valid is True
    assert result.normalized_sql is not None
    assert result.errors == ()


def test_rejects_multiple_statements():
    result = validate_sql("SELECT * FROM orders; DROP TABLE orders;")
    assert result.is_valid is False
    assert any("single statement" in e.lower() for e in result.errors)


def test_semicolon_inside_a_string_literal_is_not_mistaken_for_a_second_statement():
    """A naive `sql.split(';')` would misparse this as two statements
    and might even strip out the fake DROP as if it were real SQL. A
    real parser knows it's just string content."""
    sql = "SELECT * FROM orders WHERE status = 'PLACED; DROP TABLE orders; --'"
    result = validate_sql(sql)
    assert result.is_valid is True
    assert result.referenced_tables == ("orders",)


# ---------------------------------------------------------------------------
# 3. Read-only enforcement -- the actual security boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE orders",
        "DELETE FROM orders",
        "UPDATE orders SET status = 'CANCELLED'",
        "INSERT INTO orders (order_id) VALUES ('X1')",
        "TRUNCATE TABLE orders",
        "ALTER TABLE orders ADD COLUMN foo TEXT",
        "CREATE TABLE evil (id INT)",
        "GRANT ALL ON orders TO public",
        "VACUUM orders",
        "EXPLAIN SELECT * FROM orders",
    ],
)
def test_rejects_non_select_statements(sql):
    result = validate_sql(sql)
    assert result.is_valid is False
    assert result.normalized_sql is None


def test_rejects_dml_smuggled_inside_a_cte():
    """The outer statement is syntactically a SELECT -- only walking the
    full parsed tree (not just the root node type) catches the DELETE
    hidden inside the CTE. This is exactly the kind of thing the LLM
    prompt's 'SELECT only' instruction cannot be trusted to prevent."""
    sql = "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x"
    result = validate_sql(sql)
    assert result.is_valid is False
    assert any("disallowed operation" in e.lower() for e in result.errors)


def test_rejects_select_into():
    """SELECT INTO creates a new table -- a SELECT in name only."""
    result = validate_sql("SELECT * INTO new_table FROM orders")
    assert result.is_valid is False
    assert any("into" in e.lower() for e in result.errors)


def test_rejects_administrative_functions_even_inside_a_select():
    result = validate_sql("SELECT pg_sleep(10)")
    assert result.is_valid is False
    assert any("disallowed function" in e.lower() for e in result.errors)


def test_accepts_ctes_and_set_operations():
    result = validate_sql(
        "WITH recent AS (SELECT * FROM orders WHERE order_date > '2024-01-01') "
        "SELECT * FROM recent"
    )
    assert result.is_valid is True

    result = validate_sql("SELECT 1 AS n UNION SELECT 2 AS n")
    assert result.is_valid is True


# ---------------------------------------------------------------------------
# 4. Referenced tables + normalized SQL
# ---------------------------------------------------------------------------


def test_referenced_tables_extracted_and_cte_aliases_excluded():
    sql = "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent"
    result = validate_sql(sql)
    assert result.is_valid is True
    assert result.referenced_tables == ("orders",)  # not "recent"


def test_referenced_tables_extracted_for_multi_table_join():
    sql = (
        "SELECT o.order_id, c.full_name FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id"
    )
    result = validate_sql(sql)
    assert result.is_valid is True
    assert result.referenced_tables == ("customers", "orders")


def test_normalized_sql_is_deterministic_and_a_single_statement():
    result1 = validate_sql("select   *   from orders")
    result2 = validate_sql("SELECT * FROM orders")
    assert result1.is_valid and result2.is_valid
    assert result1.normalized_sql == result2.normalized_sql


# ---------------------------------------------------------------------------
# 5. Optional schema cross-check
# ---------------------------------------------------------------------------


def test_valid_without_schema_check_when_no_schema_given():
    result = validate_sql("SELECT * FROM not_a_real_table")
    assert result.is_valid is True  # no schema passed -> no table-existence check


def test_rejects_unknown_table_when_schema_given():
    result = validate_sql("SELECT * FROM not_a_real_table", schema=WAREHOUSE_SCHEMA)
    assert result.is_valid is False
    assert any("not_a_real_table" in e for e in result.errors)


def test_accepts_known_tables_when_schema_given():
    result = validate_sql("SELECT * FROM orders", schema=WAREHOUSE_SCHEMA)
    assert result.is_valid is True


# ---------------------------------------------------------------------------
# 6. Malformed SQL
# ---------------------------------------------------------------------------


def test_rejects_unparseable_sql():
    result = validate_sql("SELECT FROM WHERE ***")
    assert result.is_valid is False
    assert result.errors


def test_result_is_a_plain_dataclass_shape():
    result = validate_sql("SELECT 1")
    assert isinstance(result, SQLValidationResult)
    assert isinstance(result.errors, tuple)
    assert isinstance(result.referenced_tables, tuple)

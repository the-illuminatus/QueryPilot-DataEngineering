"""Converts a discovered `SchemaInfo` into concise, LLM-ready context.

This is plain text generation only -- no prompt template, no model
call, no SQL generation. Later phases (LLM generation) are expected to
embed this text verbatim into a prompt.
"""

from .models import SchemaInfo, TableInfo


def _column_line(table: TableInfo, column) -> str:
    flags = []
    if column.is_primary_key:
        flags.append("PK")
    fk = next((fk for fk in table.foreign_keys if fk.column == column.name), None)
    if fk:
        flags.append(f"FK -> {fk.references_table}.{fk.references_column}")
    if not column.nullable:
        flags.append("NOT NULL")
    suffix = f"  [{', '.join(flags)}]" if flags else ""
    return f"  - {column.name}: {column.data_type}{suffix}"


def _table_block(table: TableInfo) -> str:
    lines = [f"Table: {table.name}"]
    if table.description:
        lines.append(f"  Description: {table.description}")
    if table.primary_key:
        lines.append(f"  Primary key: {', '.join(table.primary_key)}")
    lines.extend(_column_line(table, col) for col in table.columns)
    if table.foreign_keys:
        lines.append("  Relationships:")
        lines.extend(
            f"    - {table.name}.{fk.column} -> {fk.references_table}.{fk.references_column}"
            for fk in table.foreign_keys
        )
    if table.check_constraints:
        lines.append("  Constraints:")
        lines.extend(f"    - {c}" for c in table.check_constraints)
    return "\n".join(lines)


def build_schema_context(schema: SchemaInfo) -> str:
    """Renders the full schema as a single plain-text block: one section
    per table, each listing its columns (with PK/FK/NOT NULL flags),
    foreign-key relationships, and CHECK constraints (e.g. status enums)
    exactly as PostgreSQL defines them. Deterministic given the same
    `SchemaInfo` -- table and column order both come from discovery's
    alphabetical/catalog ordering, never re-sorted here."""
    return "\n\n".join(_table_block(table) for table in schema.tables)

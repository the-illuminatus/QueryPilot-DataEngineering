"""Schema representation for the NL2SQL layer.

Plain, frozen dataclasses -- deterministic, hashable, and directly
serializable with `dataclasses.asdict()` since every field is a
primitive, tuple, or another dataclass of the same kind. This is the
shared vocabulary between schema discovery (discovery.py) and schema
context generation (context.py): discovery fills it in from PostgreSQL,
context generation reads it back out to build LLM prompt text. Neither
of those needs to know about the other.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    default: Optional[str] = None


@dataclass(frozen=True)
class ForeignKeyInfo:
    column: str
    references_table: str
    references_column: str


@dataclass(frozen=True)
class TableInfo:
    name: str
    columns: Tuple[ColumnInfo, ...]
    primary_key: Tuple[str, ...]
    foreign_keys: Tuple[ForeignKeyInfo, ...] = field(default_factory=tuple)
    check_constraints: Tuple[str, ...] = field(default_factory=tuple)
    description: Optional[str] = None

    def column(self, name: str) -> Optional[ColumnInfo]:
        return next((c for c in self.columns if c.name == name), None)


@dataclass(frozen=True)
class SchemaInfo:
    tables: Tuple[TableInfo, ...]

    def table(self, name: str) -> Optional[TableInfo]:
        return next((t for t in self.tables if t.name == name), None)

    @property
    def table_names(self) -> Tuple[str, ...]:
        return tuple(t.name for t in self.tables)

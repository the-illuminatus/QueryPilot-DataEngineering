"""NL2SQL foundation for the QueryPilot warehouse: PostgreSQL schema
discovery, LLM-ready schema context generation, provider-agnostic
LLM-based candidate SQL generation, static SQL validation, and bounded
read-only execution.

Phases covered so far: schema discovery + context generation (7A), LLM
SQL generation (7B), SQL validation / safety gate (7C), read-only
execution (7D), dashboard integration (7E), and multi-provider LLM
generation (7F). See each module's docstring for what it does and does
not do. Provider selection (Anthropic/Gemini/Ollama/OpenRouter) lives
under .providers -- generation.py and everything above it never branch
on which one is active.
"""

from .context import build_schema_context
from .discovery import discover_schema
from .execution import SQLExecutionError, SQLExecutionResult, execute_sql
from .generation import (
    MAX_QUESTION_LENGTH,
    SQLGenerationResult,
    generate_sql,
    get_configuration_error,
    validate_question_length,
)
from .models import ColumnInfo, ForeignKeyInfo, SchemaInfo, TableInfo
from .validation import SQLValidationResult, validate_sql

__all__ = [
    "discover_schema",
    "build_schema_context",
    "generate_sql",
    "get_configuration_error",
    "validate_question_length",
    "MAX_QUESTION_LENGTH",
    "SQLGenerationResult",
    "validate_sql",
    "SQLValidationResult",
    "execute_sql",
    "SQLExecutionResult",
    "SQLExecutionError",
    "SchemaInfo",
    "TableInfo",
    "ColumnInfo",
    "ForeignKeyInfo",
]

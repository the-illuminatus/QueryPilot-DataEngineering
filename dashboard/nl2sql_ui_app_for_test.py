"""Test-only Streamlit script. Drives
dashboard.nl2sql_ui.render_ask_querypilot() under Streamlit's official
`AppTest` harness, with the src/nl2sql pipeline functions replaced by
fakes so a test run never makes a real LLM API call or a real
PostgreSQL connection. Not part of the actual dashboard app -- imported
only by tests/test_nl2sql_ui.py's rendering smoke tests.

Behavior is switched by two session-state flags the test sets before
`AppTest.run()`:
  - `_test_no_key`: simulates no LLM provider being configured.
  - `_test_force_invalid`: simulates validate_sql() rejecting the SQL.

The fake generate_sql() also increments `_test_generate_call_count` in
session_state on every real invocation, so a test can assert exactly
how many times the provider was called -- e.g. to prove a rejected
(oversized or throttled) question never reached it.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from dashboard import nl2sql_ui
from src.nl2sql.execution import SQLExecutionResult
from src.nl2sql.generation import SQLGenerationResult
from src.nl2sql.models import SchemaInfo
from src.nl2sql.validation import SQLValidationResult

_no_key = st.session_state.get("_test_no_key", False)
_force_invalid = st.session_state.get("_test_force_invalid", False)

nl2sql_ui.get_configuration_error = lambda: ("NL2SQL_PROVIDER is not configured." if _no_key else None)
nl2sql_ui._discover_schema_cached = lambda engine: SchemaInfo(tables=())


def _fake_generate_sql(question, schema_context):
    # Counted in session_state (not a plain module-level variable) --
    # AppTest re-executes this whole script on every .run(), so only
    # state stored in session_state survives across reruns within one
    # AppTest session. Lets tests assert exactly how many times the
    # provider was actually invoked, e.g. to prove a throttled or
    # oversized question never reached it.
    st.session_state["_test_generate_call_count"] = st.session_state.get("_test_generate_call_count", 0) + 1
    return SQLGenerationResult(sql="SELECT 1 AS one", explanation="A fixed test query.", tables_used=["orders"])


nl2sql_ui.generate_sql = _fake_generate_sql

if _force_invalid:
    nl2sql_ui.validate_sql = lambda sql, schema=None: SQLValidationResult(
        is_valid=False, normalized_sql=None, errors=("Only read (SELECT) statements are allowed.",), referenced_tables=()
    )
else:
    nl2sql_ui.validate_sql = lambda sql, schema=None: SQLValidationResult(
        is_valid=True, normalized_sql="SELECT 1 AS one;", errors=(), referenced_tables=("orders",)
    )

nl2sql_ui.execute_sql = lambda *args, **kwargs: SQLExecutionResult(
    success=True, columns=("one",), rows=({"one": 1},), row_count=1, truncated=False, error=None, elapsed_seconds=0.01
)

nl2sql_ui.render_ask_querypilot(engine=None)

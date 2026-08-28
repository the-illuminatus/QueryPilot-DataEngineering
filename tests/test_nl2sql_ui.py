"""Tests for the 'Ask QueryPilot' dashboard section (dashboard/nl2sql_ui.py).

No real Anthropic API call and no real PostgreSQL connection: every
test mocks the four src/nl2sql pipeline functions
(discover_schema/generate_sql/validate_sql/execute_sql) at the point
dashboard.nl2sql_ui imported them, and asserts on `_run_pipeline`'s
plain-Python return value (`AskResult`) -- deliberately free of any
Streamlit widget/session-state concerns, per that function's own
docstring. A handful of tests instead exercise the real rendering path
via Streamlit's official `AppTest` harness, with the same functions
mocked, to prove the UI actually renders what `_run_pipeline` reports.
"""

from pathlib import Path
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from dashboard import nl2sql_ui
from dashboard.nl2sql_ui import _run_pipeline
from src.nl2sql import get_configuration_error
from src.nl2sql.execution import SQLExecutionResult
from src.nl2sql.generation import SQLGenerationResult
from src.nl2sql.models import ColumnInfo, SchemaInfo, TableInfo
from src.nl2sql.validation import SQLValidationResult

APP_PATH = str(Path(__file__).resolve().parent.parent / "dashboard" / "nl2sql_ui_app_for_test.py")

FAKE_SCHEMA = SchemaInfo(
    tables=(
        TableInfo(
            name="orders",
            columns=(ColumnInfo(name="order_id", data_type="VARCHAR(20)", nullable=False, is_primary_key=True),),
            primary_key=("order_id",),
        ),
    )
)


def _mock_generation(sql="SELECT 1", explanation="does a thing", tables=("orders",)):
    return SQLGenerationResult(sql=sql, explanation=explanation, tables_used=list(tables))


def _mock_validation(is_valid=True, sql="SELECT 1;", errors=(), tables=("orders",)):
    return SQLValidationResult(
        is_valid=is_valid,
        normalized_sql=sql if is_valid else None,
        errors=tuple(errors),
        referenced_tables=tuple(tables) if is_valid else (),
    )


def _mock_execution(success=True, rows=({"order_id": "O1"},), truncated=False, error=None):
    columns = tuple(rows[0].keys()) if rows else ()
    return SQLExecutionResult(
        success=success,
        columns=columns,
        rows=tuple(rows),
        row_count=len(rows),
        truncated=truncated,
        error=error,
        elapsed_seconds=0.01,
    )


# ---------------------------------------------------------------------------
# 8. Missing LLM provider configuration is handled safely
#
# get_configuration_error() (used by render_ask_querypilot() to gate the
# form) is provider-agnostic -- see tests/test_nl2sql_providers.py for
# full per-provider coverage. These two just confirm the UI-facing
# default-provider (Anthropic, when NL2SQL_PROVIDER is unset) case still
# behaves exactly as the original Claude-specific check did.
# ---------------------------------------------------------------------------


def test_not_configured_when_default_provider_has_no_key(monkeypatch):
    monkeypatch.delenv("NL2SQL_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert get_configuration_error() is not None


def test_configured_when_default_provider_has_a_key(monkeypatch):
    monkeypatch.delenv("NL2SQL_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-for-test")
    assert get_configuration_error() is None


# ---------------------------------------------------------------------------
# 1. Question submission invokes the NL2SQL pipeline (in the required order)
# ---------------------------------------------------------------------------


def test_run_pipeline_calls_each_stage_in_order(monkeypatch):
    calls = []

    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: (calls.append("discover"), FAKE_SCHEMA)[1])
    monkeypatch.setattr(nl2sql_ui, "build_schema_context", lambda schema: (calls.append("context"), "CONTEXT")[1])

    def fake_generate(question, schema_context):
        calls.append("generate")
        assert schema_context == "CONTEXT"
        return _mock_generation()

    def fake_validate(sql, schema=None):
        calls.append("validate")
        assert sql == "SELECT 1"
        return _mock_validation()

    def fake_execute(validation_result, engine=None, max_rows=None, timeout_seconds=None):
        calls.append("execute")
        return _mock_execution()

    monkeypatch.setattr(nl2sql_ui, "generate_sql", fake_generate)
    monkeypatch.setattr(nl2sql_ui, "validate_sql", fake_validate)
    monkeypatch.setattr(nl2sql_ui, "execute_sql", fake_execute)

    result = _run_pipeline(engine=Mock(), question="How many orders?")

    assert calls == ["discover", "context", "generate", "validate", "execute"]
    assert result.stage == nl2sql_ui._STAGE_SUCCESS


# ---------------------------------------------------------------------------
# 2 & 4. Generated SQL is passed through validate_sql(); valid SQL reaches execute_sql()
# ---------------------------------------------------------------------------


def test_generated_sql_is_passed_to_validate_sql(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation(sql="SELECT customer_id FROM customers"))

    received = {}

    def fake_validate(sql, schema=None):
        received["sql"] = sql
        received["schema"] = schema
        return _mock_validation()

    monkeypatch.setattr(nl2sql_ui, "validate_sql", fake_validate)
    monkeypatch.setattr(nl2sql_ui, "execute_sql", lambda *a, **k: _mock_execution())

    _run_pipeline(engine=Mock(), question="q")

    assert received["sql"] == "SELECT customer_id FROM customers"
    assert received["schema"] is FAKE_SCHEMA


def test_valid_sql_reaches_execute_sql_with_the_validation_result(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation())
    validation = _mock_validation(is_valid=True, sql="SELECT 1;")
    monkeypatch.setattr(nl2sql_ui, "validate_sql", lambda sql, schema=None: validation)

    received = {}

    def fake_execute(validation_result, engine=None, max_rows=None, timeout_seconds=None):
        received["validation_result"] = validation_result
        return _mock_execution()

    monkeypatch.setattr(nl2sql_ui, "execute_sql", fake_execute)

    result = _run_pipeline(engine=Mock(), question="q")

    assert received["validation_result"] is validation
    assert result.stage == nl2sql_ui._STAGE_SUCCESS


# ---------------------------------------------------------------------------
# 3. Invalid SQL is never passed to execute_sql()
# ---------------------------------------------------------------------------


def test_invalid_sql_never_reaches_execute_sql(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation(sql="DROP TABLE orders"))
    monkeypatch.setattr(
        nl2sql_ui, "validate_sql", lambda sql, schema=None: _mock_validation(is_valid=False, errors=["not a SELECT"])
    )

    execute_called = Mock()
    monkeypatch.setattr(nl2sql_ui, "execute_sql", execute_called)

    result = _run_pipeline(engine=Mock(), question="drop the orders table")

    execute_called.assert_not_called()
    assert result.stage == nl2sql_ui._STAGE_VALIDATION_FAILED
    assert result.validation.is_valid is False
    assert "not a SELECT" in result.validation.errors


def test_empty_generated_sql_is_unanswerable_and_never_reaches_validate_or_execute(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(
        nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation(sql="", explanation="no such data in schema")
    )
    validate_called = Mock()
    execute_called = Mock()
    monkeypatch.setattr(nl2sql_ui, "validate_sql", validate_called)
    monkeypatch.setattr(nl2sql_ui, "execute_sql", execute_called)

    result = _run_pipeline(engine=Mock(), question="what's the weather today?")

    validate_called.assert_not_called()
    execute_called.assert_not_called()
    assert result.stage == nl2sql_ui._STAGE_UNANSWERABLE
    assert result.error_message == "no such data in schema"


# ---------------------------------------------------------------------------
# 5. Execution results are represented correctly for rendering
# ---------------------------------------------------------------------------


def test_successful_execution_result_carries_rows_for_rendering(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation())
    monkeypatch.setattr(nl2sql_ui, "validate_sql", lambda sql, schema=None: _mock_validation())
    execution = _mock_execution(rows=({"order_id": "O1"}, {"order_id": "O2"}), truncated=True)
    monkeypatch.setattr(nl2sql_ui, "execute_sql", lambda *a, **k: execution)

    result = _run_pipeline(engine=Mock(), question="q")

    assert result.stage == nl2sql_ui._STAGE_SUCCESS
    assert result.execution.row_count == 2
    assert result.execution.truncated is True
    assert result.execution.rows == ({"order_id": "O1"}, {"order_id": "O2"})


def test_zero_row_result_is_still_a_success_not_an_error(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation())
    monkeypatch.setattr(nl2sql_ui, "validate_sql", lambda sql, schema=None: _mock_validation())
    monkeypatch.setattr(nl2sql_ui, "execute_sql", lambda *a, **k: _mock_execution(rows=()))

    result = _run_pipeline(engine=Mock(), question="q")

    assert result.stage == nl2sql_ui._STAGE_SUCCESS
    assert result.execution.row_count == 0


# ---------------------------------------------------------------------------
# 6. Validation errors are handled safely
# ---------------------------------------------------------------------------


def test_validation_failure_result_never_contains_raw_exception_text(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation(sql="DELETE FROM orders"))
    monkeypatch.setattr(
        nl2sql_ui,
        "validate_sql",
        lambda sql, schema=None: _mock_validation(is_valid=False, errors=["Only read (SELECT) statements are allowed."]),
    )
    monkeypatch.setattr(nl2sql_ui, "execute_sql", Mock())

    result = _run_pipeline(engine=Mock(), question="delete the orders")

    assert result.stage == nl2sql_ui._STAGE_VALIDATION_FAILED
    assert result.execution is None
    assert "Traceback" not in str(result.validation.errors)


# ---------------------------------------------------------------------------
# 7. Execution errors are handled safely (no internals leaked)
# ---------------------------------------------------------------------------


def test_execution_failure_reports_generic_message_and_logs_detail(monkeypatch, caplog):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation())
    monkeypatch.setattr(nl2sql_ui, "validate_sql", lambda sql, schema=None: _mock_validation())
    monkeypatch.setattr(
        nl2sql_ui,
        "execute_sql",
        lambda *a, **k: _mock_execution(
            success=False, rows=(), error="password authentication failed for user \"postgres\""
        ),
    )

    with caplog.at_level("ERROR"):
        result = _run_pipeline(engine=Mock(), question="q")

    assert result.stage == nl2sql_ui._STAGE_EXECUTION_FAILED
    # The user-facing message must never contain the raw DB error text.
    assert "password" not in result.error_message
    assert "postgres" not in result.error_message.lower() or "warehouse" in result.error_message.lower()
    # ... but it was logged server-side for debugging.
    assert any("password authentication failed" in r.message for r in caplog.records)


def test_execute_sql_raising_is_handled_safely_not_propagated(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)
    monkeypatch.setattr(nl2sql_ui, "generate_sql", lambda q, ctx: _mock_generation())
    monkeypatch.setattr(nl2sql_ui, "validate_sql", lambda sql, schema=None: _mock_validation())

    def boom(*a, **k):
        raise RuntimeError("connection pool exhausted at host db.internal:5432")

    monkeypatch.setattr(nl2sql_ui, "execute_sql", boom)

    result = _run_pipeline(engine=Mock(), question="q")  # must not raise

    assert result.stage == nl2sql_ui._STAGE_EXECUTION_ERROR
    assert "db.internal" not in result.error_message
    assert "5432" not in result.error_message


def test_generation_failure_is_handled_safely_not_propagated(monkeypatch):
    monkeypatch.setattr(nl2sql_ui, "_discover_schema_cached", lambda engine: FAKE_SCHEMA)

    def boom(question, schema_context):
        raise RuntimeError("Could not resolve authentication method: api_key=sk-ant-secretvalue")

    monkeypatch.setattr(nl2sql_ui, "generate_sql", boom)
    validate_called = Mock()
    monkeypatch.setattr(nl2sql_ui, "validate_sql", validate_called)

    result = _run_pipeline(engine=Mock(), question="q")  # must not raise

    validate_called.assert_not_called()
    assert result.stage == nl2sql_ui._STAGE_GENERATION_ERROR
    assert "sk-ant-secretvalue" not in result.error_message


# ---------------------------------------------------------------------------
# Rendering smoke tests via Streamlit's AppTest -- proves the UI actually
# renders what _run_pipeline reports, with the pipeline mocked out.
# ---------------------------------------------------------------------------


def test_render_shows_config_message_when_no_provider_configured(monkeypatch):
    at = AppTest.from_file(APP_PATH)
    at.session_state["_test_no_key"] = True
    at.run()
    assert not at.exception
    assert any("NL2SQL_PROVIDER" in info.value for info in at.info)
    assert len(at.text_input) == 0  # form isn't shown when unconfigured


def test_render_submitting_a_question_shows_dataframe_result():
    at = AppTest.from_file(APP_PATH)
    at.run()
    assert len(at.text_input) == 1

    at.text_input[0].input("How many orders are there?")
    at.button[0].click()
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 1
    assert any("How many orders are there?" in md.value for md in at.markdown if "Question:" in md.value)


def test_render_validation_failure_shows_error_and_no_dataframe():
    at = AppTest.from_file(APP_PATH)
    at.session_state["_test_force_invalid"] = True
    at.run()

    at.text_input[0].input("drop everything")
    at.button[0].click()
    at.run()

    assert not at.exception
    assert len(at.dataframe) == 0
    assert len(at.error) >= 1

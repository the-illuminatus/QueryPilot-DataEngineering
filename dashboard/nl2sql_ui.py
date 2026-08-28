"""'Ask QueryPilot' -- a natural-language question section for the
existing Streamlit dashboard, built entirely on top of the already-
tested src/nl2sql pipeline (Phases 7A-7D):

    discover_schema() -> build_schema_context() -> generate_sql()
        -> validate_sql() -> execute_sql()

This module is UI plumbing only. It does not generate SQL, does not
parse or validate SQL, and does not implement any safety check of its
own -- every one of those steps is exactly the function from src/nl2sql
that Phases 7A-7D already built and tested. The only SQL that ever
reaches `execute_sql()` here is a `SQLValidationResult` with
`is_valid=True` produced by `validate_sql()`; there is no other path
from a question to a database call, and this module never accepts or
runs a raw SQL string.

Reuses the dashboard's own read-only engine (dashboard/db.py, itself a
thin wrapper over src.warehouse.db.get_readonly_engine()) for both
schema discovery and execution -- no second connection path, no new
database configuration.

`_run_pipeline()` is the only function that talks to the LLM
provider/PostgreSQL, and is deliberately free of any `st.*` calls so it
can be tested as a plain function (see tests/test_nl2sql_ui.py) without
a running Streamlit app or a real LLM API call. `render_ask_querypilot()`
is the thin Streamlit shell around it: widgets, session-state wiring,
and rendering only.

This module is provider-agnostic by construction: it only ever calls
`generate_sql(question, schema_context)` and `get_configuration_error()`
from src.nl2sql -- both are provider-independent, so this file has no
branching on which LLM backend (Anthropic/Gemini/Ollama/OpenRouter) is
active. See src/nl2sql/providers/ for that selection.
"""

import logging
import time
from dataclasses import dataclass
from typing import MutableMapping, Optional

import pandas as pd
import streamlit as st
from sqlalchemy.engine import Engine

from src.nl2sql import (
    SQLExecutionResult,
    SQLGenerationResult,
    SQLValidationResult,
    build_schema_context,
    discover_schema,
    execute_sql,
    generate_sql,
    get_configuration_error,
    validate_question_length,
    validate_sql,
)

logger = logging.getLogger(__name__)

_SESSION_KEY = "ask_querypilot_result"
_SCHEMA_CACHE_TTL_SECONDS = 300
_MAX_ROWS = 200
_TIMEOUT_SECONDS = 20.0

# Per-session request throttle: a small, bounded number of generation
# requests per rolling time window, tracked entirely in Streamlit
# session state (no database, no shared/global state across sessions --
# each browser session gets its own independent budget). Conservative
# enough to stop accidental repeated-clicking / runaway LLM usage,
# generous enough that normal interactive use of the feature (a few
# questions in a row while exploring it) never trips it.
_THROTTLE_STATE_KEY = "ask_querypilot_request_timestamps"
MAX_REQUESTS_PER_WINDOW = 5
WINDOW_SECONDS = 60.0


def _check_and_record_throttle(session_state: MutableMapping, now: float) -> Optional[str]:
    """None -- and this request counted against the session's budget --
    if another generation request is allowed right now. Otherwise, a
    short, safe, user-facing message, and the request is *not* recorded
    (a rejected request doesn't consume budget). `session_state` and
    `now` are taken as parameters rather than reaching for `st.session_state`/
    `time.monotonic()` internally, so this is testable with a plain dict
    and fake timestamps -- no Streamlit runtime required (mirrors how
    `_run_pipeline` takes `engine` as a parameter for the same reason).
    Deciding and recording happen together in one place so there's no
    separate "did I remember to record this" step to get wrong."""
    timestamps = [t for t in session_state.get(_THROTTLE_STATE_KEY, []) if now - t < WINDOW_SECONDS]
    if len(timestamps) >= MAX_REQUESTS_PER_WINDOW:
        session_state[_THROTTLE_STATE_KEY] = timestamps  # still prune expired entries
        retry_after = max(1, round(WINDOW_SECONDS - (now - timestamps[0])))
        return (
            f"You've reached the limit of {MAX_REQUESTS_PER_WINDOW} questions per "
            f"{int(WINDOW_SECONDS)} seconds. Try again in about {retry_after}s."
        )
    timestamps.append(now)
    session_state[_THROTTLE_STATE_KEY] = timestamps
    return None

EXAMPLE_QUESTIONS = (
    "Which states generate the most collected revenue?",
    "What are the top 10 customers by total successful payment amount?",
    "Show monthly collected revenue for 2026.",
    "Which product categories sell the most?",
    "How many payments were made using UPI?",
    "How many orders failed reconciliation?",
)

# Stages an AskResult can end in. Only "success" has rows to show; every
# other stage is a safe, user-facing explanation of what happened and
# why nothing (or nothing further) was executed.
_STAGE_SCHEMA_ERROR = "schema_error"
_STAGE_GENERATION_ERROR = "generation_error"
_STAGE_UNANSWERABLE = "unanswerable"
_STAGE_VALIDATION_FAILED = "validation_failed"
_STAGE_EXECUTION_ERROR = "execution_error"
_STAGE_EXECUTION_FAILED = "execution_failed"
_STAGE_SUCCESS = "success"


@dataclass
class AskResult:
    """Everything needed to render the outcome of one question. Holds
    the real SQLGenerationResult/SQLValidationResult/SQLExecutionResult
    objects for display (generated SQL, explanation, tables used,
    validation errors) but `error_message` is always a pre-written,
    safe string -- never a raw exception or DB error message."""

    question: str
    stage: str
    generation: Optional[SQLGenerationResult] = None
    validation: Optional[SQLValidationResult] = None
    execution: Optional[SQLExecutionResult] = None
    error_message: Optional[str] = None


@st.cache_data(ttl=_SCHEMA_CACHE_TTL_SECONDS)
def _discover_schema_cached(_engine: Engine):
    """Cached: the warehouse schema doesn't change between questions in
    a session, so there's no reason to re-discover it on every submit.
    `_engine` (leading underscore) is Streamlit's convention for "don't
    hash this argument" -- mirrors dashboard/queries.py's `_engine`
    pattern for the same reason."""
    return discover_schema(engine=_engine)


def _run_pipeline(engine: Engine, question: str) -> AskResult:
    """Runs discover -> context -> generate -> validate -> execute for
    one question. Pure orchestration: calls only the existing
    src/nl2sql functions, in the fixed order the architecture requires,
    and never runs SQL that didn't come back from validate_sql() with
    is_valid=True. Never raises -- any failure (Claude API, database)
    is logged server-side with full detail and reported back as a
    generic, safe message."""
    try:
        schema = _discover_schema_cached(engine)
    except Exception as exc:  # noqa: BLE001 - reported safely below, logged in full here
        logger.error("Ask QueryPilot: schema discovery failed for question %r: %s", question, exc)
        return AskResult(
            question=question,
            stage=_STAGE_SCHEMA_ERROR,
            error_message="Could not read the warehouse schema. See server logs for details.",
        )
    schema_context = build_schema_context(schema)

    try:
        generation = generate_sql(question, schema_context)
    except Exception as exc:  # noqa: BLE001 - covers any provider's API/auth/network errors
        logger.error("Ask QueryPilot: SQL generation failed for question %r: %s", question, exc)
        return AskResult(
            question=question,
            stage=_STAGE_GENERATION_ERROR,
            error_message="Could not reach the configured LLM provider to generate SQL. See server logs for details.",
        )

    if not generation.sql.strip():
        return AskResult(
            question=question,
            stage=_STAGE_UNANSWERABLE,
            generation=generation,
            error_message=generation.explanation or "The question could not be translated into SQL from the current schema.",
        )

    validation = validate_sql(generation.sql, schema=schema)

    if not validation.is_valid:
        # Deliberately does not call execute_sql() at all in this branch.
        return AskResult(question=question, stage=_STAGE_VALIDATION_FAILED, generation=generation, validation=validation)

    try:
        execution = execute_sql(validation, engine=engine, max_rows=_MAX_ROWS, timeout_seconds=_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - execute_sql only raises for misuse; guard anyway
        logger.error("Ask QueryPilot: execute_sql raised for question %r: %s", question, exc)
        return AskResult(
            question=question,
            stage=_STAGE_EXECUTION_ERROR,
            generation=generation,
            validation=validation,
            error_message="Could not execute the generated query. See server logs for details.",
        )

    if not execution.success:
        logger.error("Ask QueryPilot: execution failed for question %r: %s", question, execution.error)
        return AskResult(
            question=question,
            stage=_STAGE_EXECUTION_FAILED,
            generation=generation,
            validation=validation,
            execution=execution,
            error_message="The query could not be executed against the warehouse. See server logs for details.",
        )

    return AskResult(question=question, stage=_STAGE_SUCCESS, generation=generation, validation=validation, execution=execution)


def _render_result(result: AskResult) -> None:
    st.divider()
    st.markdown(f"**Question:** {result.question}")

    if result.stage in (_STAGE_SCHEMA_ERROR, _STAGE_GENERATION_ERROR, _STAGE_EXECUTION_ERROR, _STAGE_EXECUTION_FAILED):
        st.error(result.error_message)
        if result.validation and result.validation.normalized_sql:
            with st.expander("Generated SQL"):
                st.code(result.validation.normalized_sql, language="sql")
        return

    if result.stage == _STAGE_UNANSWERABLE:
        st.info(result.error_message)
        return

    if result.stage == _STAGE_VALIDATION_FAILED:
        st.error("The generated SQL did not pass validation and was not executed.")
        for reason in result.validation.errors:
            st.markdown(f"- {reason}")
        if result.generation is not None:
            with st.expander("Generated SQL (not executed)"):
                st.code(result.generation.sql or "(empty)", language="sql")
        return

    # _STAGE_SUCCESS
    execution = result.execution
    st.markdown("##### Result")
    if execution.row_count == 0:
        st.info("The query ran successfully but returned no rows.")
    else:
        st.dataframe(pd.DataFrame(list(execution.rows)), width="stretch", hide_index=True)
        caption = f"{execution.row_count} row(s) · monetary columns are in INR"
        if execution.truncated:
            caption += f" · truncated to the first {execution.row_count}, more were available"
        st.caption(caption)

    st.write("")
    explanation_col, tables_col = st.columns([3, 1])
    with explanation_col:
        st.markdown("**Explanation**")
        st.write(result.generation.explanation or "—")
    with tables_col:
        st.markdown("**Tables used**")
        tables = result.validation.referenced_tables or result.generation.tables_used
        st.write(", ".join(tables) if tables else "—")

    with st.expander("Generated SQL (validated, executed read-only)"):
        st.code(result.validation.normalized_sql, language="sql")


def render_ask_querypilot(engine: Engine) -> None:
    """Renders the 'Ask QueryPilot' section. `engine` is the dashboard's
    existing read-only engine (dashboard/db.py) -- passed in rather than
    fetched here, so this module never opens its own connection."""
    st.subheader("Ask QueryPilot")
    st.caption(
        "Ask a question about the commerce and payments data in plain English. "
        "QueryPilot writes the SQL, checks it is read-only, runs it against the warehouse, "
        "and shows you the result alongside the query it used."
    )

    configuration_error = get_configuration_error()
    if configuration_error is not None:
        st.info(
            f"Natural-language questions need an LLM provider configured. {configuration_error} "
            "See `.env.example` for the available providers (Gemini, Ollama, Anthropic, OpenRouter)."
        )
        return

    with st.expander("Example questions"):
        for question in EXAMPLE_QUESTIONS:
            st.markdown(f"- {question}")

    with st.form("ask_querypilot_form"):
        question = st.text_input(
            "Natural-language question",
            placeholder="e.g. Which states generate the most collected revenue?",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Generate & run query")

    # Only an actual form submission runs the pipeline -- a rerun caused
    # by interacting with any other widget on the page (e.g. the batch
    # selector) leaves `submitted` False, so nothing re-executes, and
    # nothing below (length guard, throttle, the pipeline itself) runs
    # on a rerun that isn't a real submission.
    if submitted:
        question = question.strip()
        length_error = validate_question_length(question) if question else None
        throttle_error = None
        if question and length_error is None:
            # Checked (and, if allowed, recorded) only for a question
            # that's actually going to be sent to a provider -- an
            # empty or oversized question never consumes budget.
            throttle_error = _check_and_record_throttle(st.session_state, time.monotonic())

        if not question:
            st.warning("Enter a question first.")
        elif length_error is not None:
            st.warning(length_error)
        elif throttle_error is not None:
            st.warning(throttle_error)
        else:
            with st.spinner("Generating and running SQL..."):
                st.session_state[_SESSION_KEY] = _run_pipeline(engine, question)

    # The last result (successful or not) stays visible across unrelated
    # reruns -- it's only replaced on the next explicit submission.
    result: Optional[AskResult] = st.session_state.get(_SESSION_KEY)
    if result is not None:
        _render_result(result)

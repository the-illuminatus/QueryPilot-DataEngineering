# QueryPilot Data Engineering

A standalone, portfolio-focused Data Engineering pipeline for an
**India-focused digital-commerce and payments analytics warehouse**. This
project is independent of any prior application it may have originated
from — no Spring Boot/Angular, no auth. It includes a read-only analytics
dashboard (Phase 6) and a schema-aware, multi-provider NL2SQL layer
(Phase 7), both built directly on top of the pipeline and warehouse below
rather than as a separate application.

## Purpose

Demonstrate practical, credible Data Engineering fundamentals end to end:
ingesting raw data, validating and cleaning it, transforming it into a
curated dataset, loading it into an analytical store, and querying it with
SQL — without introducing infrastructure the project doesn't need.

The business domain is a synthetic Indian e-commerce marketplace:
customers across Indian cities and states, an INR-priced product
catalogue, orders, order line items, and payments (UPI-led, alongside
cards, net-banking, wallets and COD). **All monetary values are Indian
rupees (INR).** The data is generated locally with recent timestamps so
the warehouse reads as an operational store — it is synthetic and
reproducible, **not** a live or real-time feed.

## Target Architecture

```
Raw Data
   |
Ingestion
   |
Data Quality / Validation
   |
Transformation
   |
Curated Parquet
   |
PostgreSQL (analytical storage)
   |
Analytical SQL
   |
Dashboard (read-only consumption layer)
```

## Technology Stack

| Concern             | Choice                     |
|----------------------|----------------------------|
| Language             | Python                     |
| Tabular processing   | pandas                     |
| Columnar storage     | Parquet (pyarrow)          |
| Warehouse            | PostgreSQL                 |
| DB access            | SQLAlchemy / psycopg2      |
| Configuration        | Environment variables (`.env`) |
| Testing              | pytest                     |
| Dashboard            | Streamlit (Altair charts, bundled) |
| NL2SQL LLM provider  | Provider-agnostic (Anthropic / Gemini / Ollama / OpenRouter) |
| SQL safety gate      | sqlglot (AST-based validation) |

DuckDB may be added later for direct SQL-over-Parquet querying if it proves
useful — it is not a current dependency.

## Current Implementation Status

**Phase 1 — Repository cleanup & foundation:** application-specific code
(Spring Boot backend, Angular frontend, LLM/NL2SQL integration, auth)
removed; clean Python project structure; environment-variable-driven
configuration; pytest infrastructure.

**Phase 2 — Dataset contract & ingestion:** synthetic, seeded India
e-commerce dataset generator (INR pricing, Indian names/cities/states,
UPI-led payment mix, recent order dates); ingestion pipeline lands
immutable, batch-partitioned raw data.

**Phase 3 — Data quality / validation:** entity-level, referential, and
temporal validation rules; rejected rows and a JSON quality report written
per batch; accepted rows persisted for later stages to consume without
re-running validation.

**Phase 4 — Transformation & curated Parquet:** type normalization,
`order_items.line_total`, and orders-level total-amount reconciliation;
curated Parquet written per batch under `data/curated/`.

**Phase 5 — PostgreSQL warehouse:** curated batches loaded into PostgreSQL
with idempotent upserts, full batch lineage, transactional safety, and
analytical SQL.

**Phase 6 — Analytics dashboard:** a read-only Streamlit dashboard over the
warehouse — KPIs, revenue/customer/order/payment analytics, pipeline
health, and reconciliation drill-down — see below.

**Phase 7 — NL2SQL / "Ask QueryPilot" (this state):** a schema-aware
natural-language-to-SQL layer added on top of the stable warehouse and
dashboard, with its own independent SQL-safety and read-only-execution
boundaries and support for multiple LLM providers — see below.

Not yet implemented: anything beyond what's listed above (no
Airflow/Kafka/Spark/dbt/Kubernetes/auth — deliberately out of scope for
this project's size).

## Dataset & Ingestion (Phase 2)

**Domain:** a synthetic Indian e-commerce marketplace with five related
entities — `customers`, `products`, `orders`, `order_items`, `payments` —
chosen because it gives the pipeline real relational integrity, enums, and
numeric/date rules to validate in later phases.

**India localization:** customers have Indian names, a `city`, and a
`state` (an Indian state or union territory); the product catalogue uses
plausible Indian retail brands/items across marketplace categories
(Grocery, Fashion, Electronics, Smartphones, Mobile Accessories,
Appliances, …), each with its own realistic INR price band; all prices and
amounts are in **INR** with realistic per-category ranges; `payment_method`
is UPI-dominant alongside `CREDIT_CARD` / `DEBIT_CARD` / `NET_BANKING` /
`WALLET` / `COD`.

**Why synthetic data:** a public dataset rarely maps cleanly onto exactly
these five entities and gives no control over data-quality scenarios. The
generator (`scripts/generate_dataset.py`) is fully deterministic — a
single seeded `random.Random`, and every date drawn from a fixed
reference window rather than the wall clock — so running it twice on any
machine on any day produces byte-identical output, and the dataset stays
reproducible without checking large files into Git. It has **no runtime
dependencies** (no Faker); order dates are skewed toward the recent past
so the warehouse looks operational, but they are fixed constants, not
`datetime.now()`.

**"Recent" but not real-time:** the dataset is static synthetic data with
recent-looking timestamps. It is never presented as a live feed, and no
external/third-party data source is called.

**Controlled bad-data injection:** ~4% of rows per entity are deliberately
corrupted — missing required fields, duplicate primary keys, invalid
foreign keys, invalid enum values, negative/zero quantities and prices,
malformed and future-dated timestamps, duplicate customer emails. Every
injected defect corresponds to a documented validation rule, so the
majority of the dataset is valid and the data-quality stage (next phase)
has real, explainable rows to reject.

**Raw source location:** the generator writes to `data/raw/_incoming/`
(one CSV per entity) — these small files are committed to Git so the repo
is runnable without regenerating them. Everything else under `data/raw/`
is pipeline output and is gitignored.

**Regenerating the dataset** (optional — `_incoming/` is already
committed):

```bash
python scripts/generate_dataset.py    # no extra dependencies
```

**Running ingestion:**

```bash
python -m src.ingestion.pipeline
```

Ingestion reads each entity's file from `_incoming/`, checks only that it
exists, is non-empty, and has the expected columns (never inspecting the
values — that's the next stage's job), and lands it into an immutable,
batch-partitioned copy under `data/raw/<entity>/batch_id=<id>/`. One batch
id is generated per run and shared across all five entities. A run never
overwrites a previous batch, so re-running is always safe and produces a
new, independent batch. Each run also writes a JSON manifest to
`data/raw/_batches/<batch_id>.json` recording, per entity, the source
file, row count, status, output path, and detected columns.

**Validation, transformation:**

```bash
python -m src.validation.pipeline --batch-id <BATCH_ID>
python -m src.transformation.pipeline --batch-id <BATCH_ID>
```

Validation applies entity, referential, and temporal rules; accepted rows
go to `data/validated/`, rejected rows and a quality report go to
`data/rejected/`. Transformation reads only the accepted rows (it never
re-runs validation), casts them to proper types, computes
`order_items.line_total` and the orders reconciliation columns, and
writes curated Parquet to `data/curated/`.

## Warehouse & Analytics (Phase 5)

**Setup requirements:** a reachable PostgreSQL server (any recent version
— developed against PostgreSQL 17) and a database for this project to use.
Create it once, using whatever admin access you have:

```sql
CREATE DATABASE dataeng_warehouse;
```

Then set `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` /
`POSTGRES_USER` / `POSTGRES_PASSWORD` in `.env` (see `.env.example`) to
point at it. No other setup is required — the loader applies the schema
itself (idempotently) on every run; `sql/ddl/` is not something you need
to run by hand, though it's there to read.

**Running the warehouse load:**

```bash
python -m src.warehouse.pipeline --batch-id <BATCH_ID>
```

The batch must already have curated output (i.e. Phase 4 must have run
for it). The loader upserts `customers`, `products`, `orders`,
`order_items`, and `payments` — in that dependency order — inside a
single transaction, then runs post-load reconciliation checks (row
counts, primary-key uniqueness, foreign-key integrity, unexpected nulls,
monetary totals) before committing.

**Loading strategy & idempotency:** each table's natural key
(`customer_id`, `order_id`, ...) is its primary key, and loading uses
`INSERT ... ON CONFLICT DO UPDATE` — the same natural-key row loaded again
updates in place rather than duplicating. A `batch_id` column on every
table always shows which batch most recently produced that row's current
state. A separate `pipeline_batches` table is the permanent, append-only
ledger of every load attempt (batch_id, status, row counts, timestamps,
and the error if one failed) — it is never overwritten wholesale, so full
historical lineage survives even as entity tables move forward to a
newer batch's state. Re-running `--batch-id X` after it already succeeded
is refused outright with a clear error (consistent with every earlier
pipeline stage) rather than silently re-doing the work. If a load fails
partway through, the whole transaction rolls back — no batch is ever left
partially loaded — and a `FAILED` row is recorded separately so the
failure is visible and the batch can be retried.

**Analytical SQL** lives in `sql/analytics/` — eleven read-only queries
(total revenue, revenue by month/category/state, top customers, average
order value, order/payment status and payment-method distributions, and
the order-reconciliation rate plus a drill-down into specific mismatches)
that run directly against the warehouse tables. All revenue figures are
INR.

## Dashboard (Phase 6)

A read-only Streamlit dashboard consuming the warehouse and its analytical
SQL — the presentation layer over everything above it, styled as an
"India Payments & Commerce Analytics" product. It never writes to
PostgreSQL and never re-runs any pipeline stage itself. Charts are built
with Altair (which already ships with Streamlit — no added dependency);
all monetary values are shown in INR with Indian lakh/crore formatting
(`dashboard/format.py`).

**Run it:**

```bash
streamlit run dashboard/app.py
```

Needs the same `.env` PostgreSQL configuration as the warehouse loader,
and at least one successfully loaded batch.

**Layout:** a header with the "data as of" date and a data-lineage
indicator, then six tabs:

- **Overview** — KPI band (collected revenue, orders, average order
  value, payment success rate, reconciliation rate), revenue trend by
  month, revenue by category.
- **Revenue** — revenue by customer state, plus a monthly detail table.
- **Customers** — top customers by collected revenue.
- **Orders & Payments** — order-status distribution, payment-method mix
  (UPI-led), payment-status distribution.
- **Data Quality** — a batch selector over `pipeline_batches` with that
  load's row counts and its validation quality report (read directly from
  `data/rejected/batch_id=.../quality_report.json` when present — reusing
  that file rather than re-implementing validation), and a reconciliation
  mismatches table, largest discrepancy first.
- **Ask QueryPilot** — the NL2SQL section (below).

**On the batch selector — an important limitation, stated plainly rather
than hidden:** the warehouse tables are current-state (Type 1) — they
always reflect the *latest* successful load, not a historical snapshot
per batch. So the selector only changes what the pipeline-health section
shows (that specific load's own row counts/status/quality report); every
other section on the page always reflects the current warehouse state,
regardless of which batch is selected. The dashboard says this directly
rather than implying it offers historical warehouse snapshots it doesn't.

**Read-only enforcement:** every dashboard connection runs
`SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` at the Postgres
session level (`dashboard/db.py`) — not just "the code only issues
SELECTs," but a real, DB-enforced guarantee that even a coding mistake in
the dashboard cannot write to the warehouse.

**SQL reuse:** `dashboard/queries.py` reads and executes the existing
`sql/analytics/*.sql` files directly — the SQL text lives in exactly one
place. The one dashboard-specific query (batch load history, for the
selector) lives under `sql/analytics/dashboard/`, for the same reason.

## NL2SQL — "Ask QueryPilot" (Phase 7)

A schema-aware natural-language-to-SQL layer (`src/nl2sql/`), exposed as
its own section in the dashboard, that lets a user ask a plain-English
question about the warehouse and get back real data:

```
discover_schema() → build_schema_context() → generate_sql()
    → validate_sql() → execute_sql()
```

Each stage is an independent, separately-tested module — schema
discovery/context (`discovery.py`, `context.py`), LLM SQL generation
(`generation.py` + `providers/`), a static AST-based SQL safety gate
(`validation.py`, via sqlglot), and bounded read-only execution
(`execution.py`, reusing the same `SET SESSION CHARACTERISTICS AS
TRANSACTION READ ONLY` guarantee the dashboard itself uses).

**The LLM only ever produces a candidate SQL string — nothing more.** It
never executes anything and is never trusted to self-police "SELECT
only": every candidate is independently parsed into an AST and rejected
unless it's a single, genuinely read-only statement (this also catches
things a keyword filter would miss, like a write hidden inside a CTE)
*before* it ever reaches PostgreSQL, over a connection that is itself
read-only regardless. SQL validation and read-only execution are
deliberately kept as separate safety boundaries from generation — a
provider (or a bug in one) can produce bad SQL; it cannot make bad SQL
run.

### Provider Configuration

Which LLM answers a question is configured, not hardcoded — set
`NL2SQL_PROVIDER` in `.env` to one of:

| Provider     | `NL2SQL_PROVIDER` | Needs                                   | Notes |
|--------------|--------------------|------------------------------------------|-------|
| Anthropic    | `anthropic`        | `ANTHROPIC_API_KEY`                      | Default if `NL2SQL_PROVIDER` is left unset, for backward compatibility. Paid API. |
| Gemini       | `gemini`           | `GEMINI_API_KEY`                         | Preferred no-cost option — Google's free tier. |
| Ollama       | `ollama`           | `NL2SQL_MODEL` (a model you've pulled locally), optionally `OLLAMA_BASE_URL` | Fully local, no cloud key, no cost. Requires `ollama serve` running. |
| OpenRouter   | `openrouter`       | `OPENROUTER_API_KEY` + `NL2SQL_MODEL`    | OpenAI-compatible access to many models, including free ones. |

`NL2SQL_MODEL` optionally overrides the model for whichever provider is
selected (required, not optional, for Ollama and OpenRouter — see
`.env.example` for exact defaults and format per provider). Only the
selected provider's own settings are read; an unset or invalid
`NL2SQL_PROVIDER` value, or a selected provider missing its own required
setting, fails with a clear, safe message in the dashboard rather than a
crash or a stack trace.

**Credentials belong in `.env` only** (gitignored) — never in
`.env.example`, never hardcoded, never committed. `.env.example`
documents every variable above with no real values filled in.

## Project Structure

```
.
├── data/
│   ├── raw/
│   │   ├── _incoming/       # committed source-system extracts (5 CSVs)
│   │   ├── _batches/        # ingestion run manifests (gitignored)
│   │   └── <entity>/        # immutable batch-partitioned raw output (gitignored)
│   ├── validated/            # accepted rows per batch (gitignored)
│   ├── rejected/              # rejected rows + quality report per batch (gitignored)
│   ├── curated/                # curated Parquet + transformation report per batch (gitignored)
│   └── warehouse/               # warehouse load report per batch (gitignored)
├── scripts/
│   └── generate_dataset.py   # synthetic dataset generator (Faker, seeded)
├── src/
│   ├── ingestion/             # reads raw extracts, lands immutable batches
│   ├── validation/            # entity/referential/temporal rules, accepted+rejected output
│   ├── transformation/        # type casting, line_total, order reconciliation, curated Parquet
│   ├── warehouse/             # PostgreSQL schema, upsert loading, lineage, reconciliation
│   ├── catalog/                # lightweight dataset/schema metadata (not yet used)
│   └── nl2sql/                  # discovery, context, generation, validation, execution
│       └── providers/            # anthropic / gemini / ollama / openrouter adapters
├── sql/
│   ├── ddl/                    # warehouse table definitions (applied idempotently by the loader)
│   └── analytics/               # 11 read-only analytical queries
│       └── dashboard/            # dashboard-only queries (batch history, freshness)
├── dashboard/
│   ├── app.py                    # Streamlit entrypoint / tabbed page layout
│   ├── queries.py                 # reads + executes sql/analytics/*.sql, Streamlit-cached
│   ├── db.py                       # cached, read-only-enforced PostgreSQL engine
│   ├── format.py                    # INR (₹, lakh/crore) + number formatting, pure
│   ├── charts.py                     # Altair chart builders, shared palette
│   ├── components.py                  # theme CSS, KPI cards, section headers
│   └── nl2sql_ui.py                    # "Ask QueryPilot" section -- orchestrates src/nl2sql only
├── tests/                       # pytest suite (unit + real-database integration tests)
├── config/
│   └── settings.py              # environment-driven configuration
├── requirements.txt              # pipeline + dashboard runtime dependencies
├── requirements-dev.txt          # generation-time-only (Faker)
├── .streamlit/
│   └── config.toml                # dashboard theme (dark, restrained accent color)
├── .env.example
└── .gitignore
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in real values, including a reachable Postgres
pytest
python -m src.ingestion.pipeline
python -m src.validation.pipeline --batch-id <BATCH_ID>
python -m src.transformation.pipeline --batch-id <BATCH_ID>
python -m src.warehouse.pipeline --batch-id <BATCH_ID>
streamlit run dashboard/app.py
```

`<BATCH_ID>` is printed by the ingestion step (also recorded in
`data/raw/_batches/`). The warehouse step (and the dashboard) need a
running PostgreSQL server and a database created for it — see "Warehouse
& Analytics" above. The full `tests/test_warehouse.py` and
`tests/test_dashboard.py` suites also need one reachable (each creates
and drops its own throwaway database); they skip with a clear explanation
if none is configured, rather than failing.

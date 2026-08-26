-- Batch lineage / load ledger. Every load attempt is recorded here.
-- IN_PROGRESS is set within the load transaction (so entity rows have a
-- valid batch_id to reference) and updated to SUCCESS before that same
-- transaction commits; if anything fails, the whole transaction rolls
-- back and a FAILED row is written separately, so IN_PROGRESS is never
-- durably observable -- only SUCCESS or FAILED ever persist. This table
-- is never truncated or overwritten wholesale -- it is the permanent
-- history of every batch ever loaded, independent of the "current
-- state" entity tables below.

CREATE TABLE IF NOT EXISTS pipeline_batches (
    batch_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(20) NOT NULL CHECK (status IN ('IN_PROGRESS', 'SUCCESS', 'FAILED')),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    curated_row_count INTEGER,
    loaded_row_count INTEGER,
    error_message TEXT
);

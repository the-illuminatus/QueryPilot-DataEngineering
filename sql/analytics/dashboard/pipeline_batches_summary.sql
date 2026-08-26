-- All pipeline load attempts, most recent first. Used by the dashboard's
-- batch selector and pipeline-health section. Every batch ever attempted
-- appears here regardless of outcome (SUCCESS or FAILED -- IN_PROGRESS is
-- never durably observable, see sql/ddl/001_pipeline_batches.sql).

SELECT
    batch_id,
    status,
    started_at,
    completed_at,
    curated_row_count,
    loaded_row_count,
    error_message
FROM pipeline_batches
ORDER BY started_at DESC;

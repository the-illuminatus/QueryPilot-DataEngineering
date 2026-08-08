/** Payload for `POST /api/v1/query/generate` and the export endpoints. */
export interface QueryRequest {
  question: string;
}

/** Result of generating and executing a natural-language question as SQL. */
export interface QueryExecutionResult {
  sql: string;
  executionTimeMs: number;
  rowCount: number;
  columns: string[];
  rows: Record<string, unknown>[];
}

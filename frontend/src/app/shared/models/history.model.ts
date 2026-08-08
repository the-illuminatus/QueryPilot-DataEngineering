export type QueryStatus = 'SUCCESS' | 'FAILED';

/** A single past query execution, as returned by `/api/v1/history`. */
export interface QueryHistoryEntry {
  id: number;
  question: string;
  generatedSql: string;
  executionTimeMs: number;
  rowCount: number;
  status: QueryStatus;
  executedAt: string;
}

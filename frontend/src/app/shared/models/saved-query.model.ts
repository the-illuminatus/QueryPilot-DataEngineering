/** Payload for `POST /api/v1/saved-queries`. */
export interface CreateSavedQueryRequest {
  title: string;
  question: string;
  generatedSql: string;
}

/** Payload for `PUT /api/v1/saved-queries/{id}` — renames only, no other field is editable. */
export interface UpdateSavedQueryRequest {
  title: string;
}

/** Public-facing representation of a saved query. */
export interface SavedQueryResponse {
  id: number;
  title: string;
  question: string;
  generatedSql: string;
  createdAt: string;
  updatedAt: string;
}

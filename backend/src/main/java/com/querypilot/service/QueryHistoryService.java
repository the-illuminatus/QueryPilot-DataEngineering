package com.querypilot.service;

import com.querypilot.dto.response.QueryHistoryResponse;
import com.querypilot.entity.QueryStatus;

import java.util.List;

/**
 * Persists and retrieves {@link com.querypilot.entity.QueryHistory} for the
 * authenticated user. Responsible only for storage and retrieval — it never
 * generates, validates, or executes SQL. A user can only ever read or delete
 * their own history entries.
 */
public interface QueryHistoryService {

    void save(String question, String generatedSql, long executionTimeMs, int rowCount, QueryStatus status);

    List<QueryHistoryResponse> getCurrentUserHistory();

    QueryHistoryResponse getHistoryEntry(Long id);

    void deleteHistoryEntry(Long id);
}

package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Raw result of executing SQL, as returned by {@link com.querypilot.client.DatabaseClient}.
 * Carries only what the database returned — no SQL text, no timing — those
 * are added by {@link com.querypilot.service.QueryExecutionService} when it
 * builds the final {@link QueryExecutionResponse}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryExecutionResult {

    private List<String> columns;
    private List<Map<String, Object>> rows;
}

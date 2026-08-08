package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Result of executing validated SQL against the database. Kept separate from
 * {@link com.querypilot.dto.request.QueryRequest}-facing generation DTOs so
 * that generation and execution concerns never overload the same type.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryExecutionResponse {

    private String sql;
    private long executionTimeMs;
    private int rowCount;
    private List<String> columns;
    private List<Map<String, Object>> rows;
}

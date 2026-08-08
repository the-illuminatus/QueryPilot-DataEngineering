package com.querypilot.service;

import com.querypilot.dto.response.QueryExecutionResponse;
import org.springframework.core.io.Resource;

/**
 * Orchestrates rendering an already-executed query's results into a
 * downloadable file. Never executes SQL itself — it only ever formats a
 * {@link QueryExecutionResponse} the caller already obtained from
 * {@link QueryExecutionService}.
 */
public interface ExportService {

    Resource exportToCsv(QueryExecutionResponse response);

    Resource exportToExcel(QueryExecutionResponse response);
}

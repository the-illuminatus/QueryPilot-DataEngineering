package com.querypilot.service;

import com.querypilot.dto.response.QueryExecutionResponse;

/**
 * Executes already-validated SQL through {@link com.querypilot.client.DatabaseClient}
 * and builds the execution response. Never generates or validates SQL —
 * callers must pass SQL that has already been through
 * {@link com.querypilot.validator.SQLValidator}.
 */
public interface QueryExecutionService {

    QueryExecutionResponse execute(String sql);
}

package com.querypilot.service;

import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.QueryExecutionResponse;

/**
 * Orchestrates the full NL2SQL flow for a user's natural language question:
 * builds a prompt, generates SQL via {@link com.querypilot.client.LLMClient},
 * validates it through {@link com.querypilot.validator.SQLValidator}, and
 * executes it via {@link QueryExecutionService}. There is no code path that
 * executes SQL without first passing validation.
 */
public interface QueryService {

    QueryExecutionResponse executeQuery(QueryRequest request);
}

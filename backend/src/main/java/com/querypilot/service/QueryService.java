package com.querypilot.service;

import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.QueryResponse;

/**
 * Generates SQL for a user's natural language question. Composes
 * {@link PromptService} with {@link com.querypilot.client.LLMClient} — never
 * validates or executes the generated SQL.
 */
public interface QueryService {

    QueryResponse generateSql(QueryRequest request);
}

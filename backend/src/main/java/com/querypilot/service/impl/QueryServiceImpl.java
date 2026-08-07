package com.querypilot.service.impl;

import com.querypilot.client.LLMClient;
import com.querypilot.dto.request.LLMRequest;
import com.querypilot.dto.request.PromptRequest;
import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.LLMResponse;
import com.querypilot.dto.response.PromptResponse;
import com.querypilot.dto.response.QueryResponse;
import com.querypilot.service.PromptService;
import com.querypilot.service.QueryService;
import com.querypilot.validator.SQLValidator;
import org.springframework.stereotype.Service;

/**
 * Default {@link QueryService} implementation. Depends only on
 * {@link PromptService}, the {@link LLMClient} abstraction, and
 * {@link SQLValidator} — never on {@code GeminiClient},
 * {@code DefaultSQLValidator}, or any other implementation-specific type.
 */
@Service
public class QueryServiceImpl implements QueryService {

    private final PromptService promptService;
    private final LLMClient llmClient;
    private final SQLValidator sqlValidator;

    public QueryServiceImpl(PromptService promptService, LLMClient llmClient, SQLValidator sqlValidator) {
        this.promptService = promptService;
        this.llmClient = llmClient;
        this.sqlValidator = sqlValidator;
    }

    @Override
    public QueryResponse generateSql(QueryRequest request) {
        PromptResponse prompt = promptService.buildPrompt(
                PromptRequest.builder().question(request.getQuestion()).build());

        LLMResponse llmResponse = llmClient.generate(
                LLMRequest.builder().prompt(prompt.getPrompt()).build());

        sqlValidator.validate(llmResponse.getContent());

        return QueryResponse.builder().sql(llmResponse.getContent()).build();
    }
}

package com.querypilot.service.impl;

import com.querypilot.client.LLMClient;
import com.querypilot.dto.request.LLMRequest;
import com.querypilot.dto.request.PromptRequest;
import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.LLMResponse;
import com.querypilot.dto.response.PromptResponse;
import com.querypilot.dto.response.QueryExecutionResponse;
import com.querypilot.entity.QueryStatus;
import com.querypilot.service.PromptService;
import com.querypilot.service.QueryExecutionService;
import com.querypilot.service.QueryHistoryService;
import com.querypilot.service.QueryService;
import com.querypilot.validator.SQLValidator;
import org.springframework.stereotype.Service;

/**
 * Default {@link QueryService} implementation. Depends only on
 * {@link PromptService}, the {@link LLMClient} abstraction,
 * {@link SQLValidator}, {@link QueryExecutionService}, and
 * {@link QueryHistoryService} — never on {@code GeminiClient},
 * {@code DefaultSQLValidator}, {@code DatabaseClient}, or any other
 * implementation-specific type.
 */
@Service
public class QueryServiceImpl implements QueryService {

    private final PromptService promptService;
    private final LLMClient llmClient;
    private final SQLValidator sqlValidator;
    private final QueryExecutionService queryExecutionService;
    private final QueryHistoryService queryHistoryService;

    public QueryServiceImpl(PromptService promptService, LLMClient llmClient, SQLValidator sqlValidator,
            QueryExecutionService queryExecutionService, QueryHistoryService queryHistoryService) {
        this.promptService = promptService;
        this.llmClient = llmClient;
        this.sqlValidator = sqlValidator;
        this.queryExecutionService = queryExecutionService;
        this.queryHistoryService = queryHistoryService;
    }

    @Override
    public QueryExecutionResponse executeQuery(QueryRequest request) {
        PromptResponse prompt = promptService.buildPrompt(
                PromptRequest.builder().question(request.getQuestion()).build());

        LLMResponse llmResponse = llmClient.generate(
                LLMRequest.builder().prompt(prompt.getPrompt()).build());

        sqlValidator.validate(llmResponse.getContent());

        QueryExecutionResponse response = queryExecutionService.execute(llmResponse.getContent());

        queryHistoryService.save(request.getQuestion(), llmResponse.getContent(), response.getExecutionTimeMs(),
                response.getRowCount(), QueryStatus.SUCCESS);

        return response;
    }
}

package com.querypilot.service.impl;

import com.querypilot.client.DatabaseClient;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.response.QueryExecutionResponse;
import com.querypilot.dto.response.QueryExecutionResult;
import com.querypilot.exception.QueryExecutionException;
import com.querypilot.service.QueryExecutionService;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

/**
 * Default {@link QueryExecutionService} implementation. Depends only on
 * {@link DatabaseClient} — never on a specific database vendor — and adds
 * timing and response assembly around it.
 */
@Service
public class QueryExecutionServiceImpl implements QueryExecutionService {

    private final DatabaseClient databaseClient;

    public QueryExecutionServiceImpl(DatabaseClient databaseClient) {
        this.databaseClient = databaseClient;
    }

    @Override
    public QueryExecutionResponse execute(String sql) {
        long startTime = System.currentTimeMillis();
        QueryExecutionResult result;
        try {
            result = databaseClient.execute(sql);
        } catch (DataAccessException ex) {
            // Covers a missing table/column (BadSqlGrammarException), an
            // unavailable database or dropped connection
            // (DataAccessResourceFailureException), and a query timeout
            // (QueryTimeoutException) — all subtypes of DataAccessException.
            // The underlying message is never exposed to the caller.
            throw new QueryExecutionException(ApplicationConstants.SQL_EXECUTION_FAILED_MESSAGE, ex);
        }
        long executionTimeMs = System.currentTimeMillis() - startTime;

        return QueryExecutionResponse.builder()
                .sql(sql)
                .executionTimeMs(executionTimeMs)
                .rowCount(result.getRows().size())
                .columns(result.getColumns())
                .rows(result.getRows())
                .build();
    }
}

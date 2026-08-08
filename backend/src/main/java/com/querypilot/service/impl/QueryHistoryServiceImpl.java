package com.querypilot.service.impl;

import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.response.QueryHistoryResponse;
import com.querypilot.entity.QueryHistory;
import com.querypilot.entity.QueryStatus;
import com.querypilot.exception.ResourceNotFoundException;
import com.querypilot.repository.QueryHistoryRepository;
import com.querypilot.service.QueryHistoryService;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Default {@link QueryHistoryService} implementation. Depends only on
 * {@link QueryHistoryRepository}. The authenticated user's email is read
 * from the {@link SecurityContextHolder} populated by the existing JWT
 * filter — every read and delete is scoped to it, so a user can never reach
 * another user's history entry.
 */
@Service
public class QueryHistoryServiceImpl implements QueryHistoryService {

    private final QueryHistoryRepository queryHistoryRepository;

    public QueryHistoryServiceImpl(QueryHistoryRepository queryHistoryRepository) {
        this.queryHistoryRepository = queryHistoryRepository;
    }

    @Override
    public void save(String question, String generatedSql, long executionTimeMs, int rowCount, QueryStatus status) {
        QueryHistory history = QueryHistory.builder()
                .userEmail(currentUserEmail())
                .question(question)
                .generatedSql(generatedSql)
                .executionTimeMs(executionTimeMs)
                .rowCount(rowCount)
                .status(status)
                .build();
        queryHistoryRepository.save(history);
    }

    @Override
    public List<QueryHistoryResponse> getCurrentUserHistory() {
        return queryHistoryRepository.findByUserEmailOrderByExecutedAtDesc(currentUserEmail()).stream()
                .map(this::toResponse)
                .toList();
    }

    @Override
    public QueryHistoryResponse getHistoryEntry(Long id) {
        return toResponse(findOwnedEntry(id));
    }

    @Override
    public void deleteHistoryEntry(Long id) {
        queryHistoryRepository.delete(findOwnedEntry(id));
    }

    private QueryHistory findOwnedEntry(Long id) {
        QueryHistory history = queryHistoryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException(ApplicationConstants.HISTORY_NOT_FOUND_MESSAGE));

        // A mismatched owner is reported identically to a missing entry so
        // that a user probing other IDs learns nothing about their existence.
        if (!history.getUserEmail().equalsIgnoreCase(currentUserEmail())) {
            throw new ResourceNotFoundException(ApplicationConstants.HISTORY_NOT_FOUND_MESSAGE);
        }
        return history;
    }

    private String currentUserEmail() {
        return SecurityContextHolder.getContext().getAuthentication().getName();
    }

    private QueryHistoryResponse toResponse(QueryHistory history) {
        return QueryHistoryResponse.builder()
                .id(history.getId())
                .question(history.getQuestion())
                .generatedSql(history.getGeneratedSql())
                .executionTimeMs(history.getExecutionTimeMs())
                .rowCount(history.getRowCount())
                .status(history.getStatus())
                .executedAt(history.getExecutedAt())
                .build();
    }
}

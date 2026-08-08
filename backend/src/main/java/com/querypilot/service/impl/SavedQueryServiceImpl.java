package com.querypilot.service.impl;

import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.CreateSavedQueryRequest;
import com.querypilot.dto.request.UpdateSavedQueryRequest;
import com.querypilot.dto.response.SavedQueryResponse;
import com.querypilot.entity.SavedQuery;
import com.querypilot.exception.BusinessException;
import com.querypilot.exception.ResourceNotFoundException;
import com.querypilot.repository.SavedQueryRepository;
import com.querypilot.service.SavedQueryService;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Default {@link SavedQueryService} implementation. Depends only on
 * {@link SavedQueryRepository}. The authenticated user's email is read from
 * the {@link SecurityContextHolder} populated by the existing JWT filter —
 * every read, update, and delete is scoped to it, so a user can never reach
 * another user's saved query.
 */
@Service
public class SavedQueryServiceImpl implements SavedQueryService {

    private final SavedQueryRepository savedQueryRepository;

    public SavedQueryServiceImpl(SavedQueryRepository savedQueryRepository) {
        this.savedQueryRepository = savedQueryRepository;
    }

    @Override
    public SavedQueryResponse save(CreateSavedQueryRequest request) {
        String userEmail = currentUserEmail();

        if (savedQueryRepository.existsByUserEmailAndTitle(userEmail, request.getTitle())) {
            throw new BusinessException(ApplicationConstants.SAVED_QUERY_TITLE_DUPLICATE_MESSAGE);
        }

        SavedQuery savedQuery = SavedQuery.builder()
                .userEmail(userEmail)
                .title(request.getTitle())
                .question(request.getQuestion())
                .generatedSql(request.getGeneratedSql())
                .build();

        return toResponse(savedQueryRepository.save(savedQuery));
    }

    @Override
    public List<SavedQueryResponse> getCurrentUserSavedQueries() {
        return savedQueryRepository.findByUserEmailOrderByUpdatedAtDesc(currentUserEmail()).stream()
                .map(this::toResponse)
                .toList();
    }

    @Override
    public SavedQueryResponse getSavedQuery(Long id) {
        return toResponse(findOwnedEntry(id));
    }

    @Override
    public SavedQueryResponse updateTitle(Long id, UpdateSavedQueryRequest request) {
        SavedQuery savedQuery = findOwnedEntry(id);

        if (!savedQuery.getTitle().equals(request.getTitle())
                && savedQueryRepository.existsByUserEmailAndTitle(savedQuery.getUserEmail(), request.getTitle())) {
            throw new BusinessException(ApplicationConstants.SAVED_QUERY_TITLE_DUPLICATE_MESSAGE);
        }

        savedQuery.setTitle(request.getTitle());
        return toResponse(savedQueryRepository.save(savedQuery));
    }

    @Override
    public void deleteSavedQuery(Long id) {
        savedQueryRepository.delete(findOwnedEntry(id));
    }

    private SavedQuery findOwnedEntry(Long id) {
        SavedQuery savedQuery = savedQueryRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException(ApplicationConstants.SAVED_QUERY_NOT_FOUND_MESSAGE));

        // A mismatched owner is reported identically to a missing entry so
        // that a user probing other IDs learns nothing about their existence.
        if (!savedQuery.getUserEmail().equalsIgnoreCase(currentUserEmail())) {
            throw new ResourceNotFoundException(ApplicationConstants.SAVED_QUERY_NOT_FOUND_MESSAGE);
        }
        return savedQuery;
    }

    private String currentUserEmail() {
        return SecurityContextHolder.getContext().getAuthentication().getName();
    }

    private SavedQueryResponse toResponse(SavedQuery savedQuery) {
        return SavedQueryResponse.builder()
                .id(savedQuery.getId())
                .title(savedQuery.getTitle())
                .question(savedQuery.getQuestion())
                .generatedSql(savedQuery.getGeneratedSql())
                .createdAt(savedQuery.getCreatedAt())
                .updatedAt(savedQuery.getUpdatedAt())
                .build();
    }
}

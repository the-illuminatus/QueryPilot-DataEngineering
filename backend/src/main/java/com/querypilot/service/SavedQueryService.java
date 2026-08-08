package com.querypilot.service;

import com.querypilot.dto.request.CreateSavedQueryRequest;
import com.querypilot.dto.request.UpdateSavedQueryRequest;
import com.querypilot.dto.response.SavedQueryResponse;

import java.util.List;

/**
 * Persists and retrieves {@link com.querypilot.entity.SavedQuery} for the
 * authenticated user, independent of {@link QueryHistoryService}. Ownership
 * is enforced here: a user can only ever read, update, or delete their own
 * saved queries.
 */
public interface SavedQueryService {

    SavedQueryResponse save(CreateSavedQueryRequest request);

    List<SavedQueryResponse> getCurrentUserSavedQueries();

    SavedQueryResponse getSavedQuery(Long id);

    SavedQueryResponse updateTitle(Long id, UpdateSavedQueryRequest request);

    void deleteSavedQuery(Long id);
}

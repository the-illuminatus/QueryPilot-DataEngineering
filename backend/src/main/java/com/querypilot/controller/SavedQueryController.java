package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.CreateSavedQueryRequest;
import com.querypilot.dto.request.UpdateSavedQueryRequest;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.SavedQueryResponse;
import com.querypilot.service.SavedQueryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Exposes the authenticated user's saved queries. Holds no business logic —
 * every request is delegated straight to {@link SavedQueryService}.
 * Protected by the existing JWT authentication like every non-{@code /auth}
 * endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/saved-queries")
@Tag(name = "Saved Queries", description = "Queries the authenticated user has chosen to keep for future reuse, independent of query history.")
public class SavedQueryController {

    private final SavedQueryService savedQueryService;

    public SavedQueryController(SavedQueryService savedQueryService) {
        this.savedQueryService = savedQueryService;
    }

    @PostMapping
    @Operation(summary = "Save a query for future reuse")
    public ResponseEntity<ApiResponse<SavedQueryResponse>> create(@Valid @RequestBody CreateSavedQueryRequest request) {
        SavedQueryResponse response = savedQueryService.save(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(ApplicationConstants.SAVED_QUERY_CREATED_SUCCESS_MESSAGE, response));
    }

    @GetMapping
    @Operation(summary = "List the authenticated user's saved queries, most recently updated first")
    public ResponseEntity<ApiResponse<List<SavedQueryResponse>>> getSavedQueries() {
        return ResponseEntity.ok(ApiResponse.success(savedQueryService.getCurrentUserSavedQueries()));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get one saved query")
    public ResponseEntity<ApiResponse<SavedQueryResponse>> getSavedQuery(@PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(savedQueryService.getSavedQuery(id)));
    }

    @PutMapping("/{id}")
    @Operation(summary = "Rename a saved query")
    public ResponseEntity<ApiResponse<SavedQueryResponse>> updateTitle(@PathVariable Long id,
            @Valid @RequestBody UpdateSavedQueryRequest request) {
        SavedQueryResponse response = savedQueryService.updateTitle(id, request);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.SAVED_QUERY_UPDATED_SUCCESS_MESSAGE, response));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete a saved query")
    public ResponseEntity<ApiResponse<Void>> deleteSavedQuery(@PathVariable Long id) {
        savedQueryService.deleteSavedQuery(id);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.SAVED_QUERY_DELETED_SUCCESS_MESSAGE, null));
    }
}

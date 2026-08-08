package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.QueryHistoryResponse;
import com.querypilot.service.QueryHistoryService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Exposes the authenticated user's query history. Holds no business logic —
 * every request is delegated straight to {@link QueryHistoryService}.
 * Protected by the existing JWT authentication like every non-{@code /auth}
 * endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/history")
@Tag(name = "Query History", description = "Records of the authenticated user's past successful query executions.")
public class QueryHistoryController {

    private final QueryHistoryService queryHistoryService;

    public QueryHistoryController(QueryHistoryService queryHistoryService) {
        this.queryHistoryService = queryHistoryService;
    }

    @GetMapping
    @Operation(summary = "List the authenticated user's query history, newest first")
    public ResponseEntity<ApiResponse<List<QueryHistoryResponse>>> getHistory() {
        return ResponseEntity.ok(ApiResponse.success(queryHistoryService.getCurrentUserHistory()));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Get one query history entry")
    public ResponseEntity<ApiResponse<QueryHistoryResponse>> getHistoryEntry(@PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(queryHistoryService.getHistoryEntry(id)));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete one query history entry")
    public ResponseEntity<ApiResponse<Void>> deleteHistoryEntry(@PathVariable Long id) {
        queryHistoryService.deleteHistoryEntry(id);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.HISTORY_DELETED_SUCCESS_MESSAGE, null));
    }
}

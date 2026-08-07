package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.QueryResponse;
import com.querypilot.service.QueryService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes NL2SQL generation. Holds no business logic — every request is
 * delegated straight to {@link QueryService}. Protected by the existing JWT
 * authentication like every non-{@code /auth} endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/query")
public class QueryController {

    private final QueryService queryService;

    public QueryController(QueryService queryService) {
        this.queryService = queryService;
    }

    @PostMapping("/generate")
    public ResponseEntity<ApiResponse<QueryResponse>> generate(@Valid @RequestBody QueryRequest request) {
        QueryResponse response = queryService.generateSql(request);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.SQL_GENERATED_SUCCESS_MESSAGE, response));
    }
}

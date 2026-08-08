package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.QueryRequest;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.QueryExecutionResponse;
import com.querypilot.service.ExportService;
import com.querypilot.service.QueryService;
import jakarta.validation.Valid;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes NL2SQL generation, execution, and result export. Holds no business
 * logic — every request is delegated straight to {@link QueryService} and
 * {@link ExportService}. Protected by the existing JWT authentication like
 * every non-{@code /auth} endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/query")
public class QueryController {

    private final QueryService queryService;
    private final ExportService exportService;

    public QueryController(QueryService queryService, ExportService exportService) {
        this.queryService = queryService;
        this.exportService = exportService;
    }

    @PostMapping("/generate")
    public ResponseEntity<ApiResponse<QueryExecutionResponse>> generate(@Valid @RequestBody QueryRequest request) {
        QueryExecutionResponse response = queryService.executeQuery(request);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.QUERY_EXECUTED_SUCCESS_MESSAGE, response));
    }

    @PostMapping("/export/csv")
    public ResponseEntity<Resource> exportCsv(@Valid @RequestBody QueryRequest request) {
        QueryExecutionResponse response = queryService.executeQuery(request);
        Resource file = exportService.exportToCsv(response);

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + ApiConstants.CSV_EXPORT_FILENAME + "\"")
                .contentType(MediaType.parseMediaType(ApiConstants.CONTENT_TYPE_CSV))
                .body(file);
    }

    @PostMapping("/export/excel")
    public ResponseEntity<Resource> exportExcel(@Valid @RequestBody QueryRequest request) {
        QueryExecutionResponse response = queryService.executeQuery(request);
        Resource file = exportService.exportToExcel(response);

        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + ApiConstants.XLSX_EXPORT_FILENAME + "\"")
                .contentType(MediaType.parseMediaType(ApiConstants.CONTENT_TYPE_XLSX))
                .body(file);
    }
}

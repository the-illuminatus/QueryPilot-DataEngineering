package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.MetadataHealthResponse;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;
import com.querypilot.service.MetadataService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes database metadata discovery. Holds no business logic — every
 * request is delegated straight to {@link MetadataService}. Protected by
 * the existing JWT authentication like every non-{@code /auth} endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/metadata")
public class MetadataController {

    private final MetadataService metadataService;

    public MetadataController(MetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @GetMapping("/schemas")
    public ResponseEntity<ApiResponse<MetadataResponse>> listSchemas() {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getDatabaseMetadata()));
    }

    @GetMapping("/schemas/{schema}")
    public ResponseEntity<ApiResponse<SchemaMetadataResponse>> getSchema(@PathVariable String schema) {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getSchemaMetadata(schema)));
    }

    @GetMapping("/tables/{schema}/{table}")
    public ResponseEntity<ApiResponse<TableMetadataResponse>> getTable(@PathVariable String schema,
                                                                        @PathVariable String table) {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getTableMetadata(schema, table)));
    }

    @GetMapping("/health")
    public ResponseEntity<ApiResponse<MetadataHealthResponse>> health() {
        return ResponseEntity.ok(ApiResponse.success(metadataService.checkHealth()));
    }
}

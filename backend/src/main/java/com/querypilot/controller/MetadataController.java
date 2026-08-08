package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.MetadataHealthResponse;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;
import com.querypilot.service.MetadataService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
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
@Tag(name = "Metadata", description = "Live PostgreSQL schema discovery: schemas, tables, views, columns, keys, and indexes.")
public class MetadataController {

    private final MetadataService metadataService;

    public MetadataController(MetadataService metadataService) {
        this.metadataService = metadataService;
    }

    @GetMapping("/schemas")
    @Operation(summary = "List every schema with its tables and views")
    public ResponseEntity<ApiResponse<MetadataResponse>> listSchemas() {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getDatabaseMetadata()));
    }

    @GetMapping("/schemas/{schema}")
    @Operation(summary = "Get one schema's tables and views")
    public ResponseEntity<ApiResponse<SchemaMetadataResponse>> getSchema(@PathVariable String schema) {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getSchemaMetadata(schema)));
    }

    @GetMapping("/tables/{schema}/{table}")
    @Operation(summary = "Get columns, primary key, foreign keys, and indexes for one table or view")
    public ResponseEntity<ApiResponse<TableMetadataResponse>> getTable(@PathVariable String schema,
                                                                        @PathVariable String table) {
        return ResponseEntity.ok(ApiResponse.success(metadataService.getTableMetadata(schema, table)));
    }

    @GetMapping("/health")
    @Operation(summary = "Check database connectivity and report the product name and version")
    public ResponseEntity<ApiResponse<MetadataHealthResponse>> health() {
        return ResponseEntity.ok(ApiResponse.success(metadataService.checkHealth()));
    }
}

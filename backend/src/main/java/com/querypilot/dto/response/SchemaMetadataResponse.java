package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * Metadata for a single schema: its tables and views (shallow — name and
 * type only; fetch a table's own endpoint for full column/key/index detail).
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SchemaMetadataResponse {

    private String schemaName;

    @Builder.Default
    private List<TableMetadataResponse> tables = new ArrayList<>();

    @Builder.Default
    private List<TableMetadataResponse> views = new ArrayList<>();
}

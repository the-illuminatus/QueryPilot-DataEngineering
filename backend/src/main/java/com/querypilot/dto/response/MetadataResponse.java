package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * Top-level snapshot of the connected database: product identity plus every
 * user schema and its tables/views.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MetadataResponse {

    private String databaseProductName;
    private String databaseProductVersion;

    @Builder.Default
    private List<SchemaMetadataResponse> schemas = new ArrayList<>();
}

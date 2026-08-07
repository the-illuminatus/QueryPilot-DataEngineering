package com.querypilot.service;

import com.querypilot.dto.response.MetadataHealthResponse;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;

/**
 * Retrieves database metadata via {@link com.querypilot.client.MetadataClient}.
 * Pure retrieval and composition — no business rules, no caching, no
 * persistence.
 */
public interface MetadataService {

    MetadataResponse getDatabaseMetadata();

    SchemaMetadataResponse getSchemaMetadata(String schema);

    TableMetadataResponse getTableMetadata(String schema, String table);

    MetadataHealthResponse checkHealth();
}

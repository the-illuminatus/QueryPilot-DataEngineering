package com.querypilot.service.impl;

import com.querypilot.client.MetadataClient;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.response.MetadataHealthResponse;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;
import com.querypilot.exception.ResourceNotFoundException;
import com.querypilot.service.MetadataService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Default {@link MetadataService} implementation. Depends only on
 * {@link MetadataClient} — never on a specific database vendor — and simply
 * composes its results into response DTOs.
 */
@Service
public class MetadataServiceImpl implements MetadataService {

    private final MetadataClient metadataClient;

    public MetadataServiceImpl(MetadataClient metadataClient) {
        this.metadataClient = metadataClient;
    }

    @Override
    public MetadataResponse getDatabaseMetadata() {
        List<SchemaMetadataResponse> schemas = metadataClient.listSchemas().stream()
                .map(this::buildSchemaMetadata)
                .toList();

        return MetadataResponse.builder()
                .databaseProductName(metadataClient.getDatabaseProductName())
                .databaseProductVersion(metadataClient.getDatabaseProductVersion())
                .schemas(schemas)
                .build();
    }

    @Override
    public SchemaMetadataResponse getSchemaMetadata(String schema) {
        if (!metadataClient.listSchemas().contains(schema)) {
            throw new ResourceNotFoundException(ApplicationConstants.SCHEMA_NOT_FOUND_MESSAGE);
        }
        return buildSchemaMetadata(schema);
    }

    @Override
    public TableMetadataResponse getTableMetadata(String schema, String table) {
        String tableType = resolveTableType(schema, table);

        return TableMetadataResponse.builder()
                .tableName(table)
                .tableType(tableType)
                .columns(metadataClient.listColumns(schema, table))
                .primaryKey(metadataClient.getPrimaryKey(schema, table))
                .foreignKeys(metadataClient.listForeignKeys(schema, table))
                .indexes(metadataClient.listIndexes(schema, table))
                .build();
    }

    @Override
    public MetadataHealthResponse checkHealth() {
        return MetadataHealthResponse.builder()
                .status("UP")
                .databaseProductName(metadataClient.getDatabaseProductName())
                .databaseProductVersion(metadataClient.getDatabaseProductVersion())
                .build();
    }

    private SchemaMetadataResponse buildSchemaMetadata(String schema) {
        return SchemaMetadataResponse.builder()
                .schemaName(schema)
                .tables(metadataClient.listTables(schema))
                .views(metadataClient.listViews(schema))
                .build();
    }

    private String resolveTableType(String schema, String table) {
        boolean isTable = metadataClient.listTables(schema).stream()
                .anyMatch(t -> t.getTableName().equalsIgnoreCase(table));
        if (isTable) {
            return "TABLE";
        }

        boolean isView = metadataClient.listViews(schema).stream()
                .anyMatch(t -> t.getTableName().equalsIgnoreCase(table));
        if (isView) {
            return "VIEW";
        }

        throw new ResourceNotFoundException(ApplicationConstants.TABLE_NOT_FOUND_MESSAGE);
    }
}

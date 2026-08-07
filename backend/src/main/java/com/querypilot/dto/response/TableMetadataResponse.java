package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * Metadata for a single table or view. When listed as part of a schema
 * ({@link SchemaMetadataResponse}), only {@code tableName}/{@code tableType}
 * are populated; the detail endpoint for one specific table populates
 * columns, keys, and indexes as well.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TableMetadataResponse {

    private String tableName;
    private String tableType;

    @Builder.Default
    private List<ColumnMetadataResponse> columns = new ArrayList<>();

    private PrimaryKeyResponse primaryKey;

    @Builder.Default
    private List<ForeignKeyResponse> foreignKeys = new ArrayList<>();

    @Builder.Default
    private List<IndexResponse> indexes = new ArrayList<>();
}

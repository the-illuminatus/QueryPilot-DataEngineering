package com.querypilot.client;

import com.querypilot.dto.response.ColumnMetadataResponse;
import com.querypilot.dto.response.ForeignKeyResponse;
import com.querypilot.dto.response.IndexResponse;
import com.querypilot.dto.response.PrimaryKeyResponse;
import com.querypilot.dto.response.TableMetadataResponse;

import java.util.List;

/**
 * Abstraction over database catalog introspection. The rest of the
 * application depends on this interface, never on a specific vendor's
 * implementation — {@code PostgresMetadataClient} is the only implementation
 * today, but additional database vendors can be added later without
 * touching any caller.
 */
public interface MetadataClient {

    String getDatabaseProductName();

    String getDatabaseProductVersion();

    List<String> listSchemas();

    List<TableMetadataResponse> listTables(String schema);

    List<TableMetadataResponse> listViews(String schema);

    List<ColumnMetadataResponse> listColumns(String schema, String table);

    PrimaryKeyResponse getPrimaryKey(String schema, String table);

    List<ForeignKeyResponse> listForeignKeys(String schema, String table);

    List<IndexResponse> listIndexes(String schema, String table);
}

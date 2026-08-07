package com.querypilot.client;

import com.querypilot.dto.response.ColumnMetadataResponse;
import com.querypilot.dto.response.ForeignKeyResponse;
import com.querypilot.dto.response.IndexResponse;
import com.querypilot.dto.response.PrimaryKeyResponse;
import com.querypilot.dto.response.TableMetadataResponse;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * PostgreSQL implementation of {@link MetadataClient}, built entirely on the
 * standard {@link DatabaseMetaData} JDBC API rather than Postgres-specific
 * SQL. All Postgres-specific decisions — namely which schemas are internal
 * system catalogs — are confined to this class.
 */
@Component
public class PostgresMetadataClient implements MetadataClient {

    private static final Set<String> SYSTEM_SCHEMAS = Set.of("pg_catalog", "information_schema", "pg_toast");
    private static final String SYSTEM_TEMP_SCHEMA_PREFIX = "pg_temp_";
    private static final String SYSTEM_TOAST_TEMP_SCHEMA_PREFIX = "pg_toast_temp_";

    private static final String TABLE_TYPE = "TABLE";
    private static final String VIEW_TYPE = "VIEW";

    private final DataSource dataSource;

    public PostgresMetadataClient(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public String getDatabaseProductName() {
        return withMetaData(DatabaseMetaData::getDatabaseProductName);
    }

    @Override
    public String getDatabaseProductVersion() {
        return withMetaData(DatabaseMetaData::getDatabaseProductVersion);
    }

    @Override
    public List<String> listSchemas() {
        return withMetaData(metaData -> {
            List<String> schemas = new ArrayList<>();
            try (ResultSet rs = metaData.getSchemas()) {
                while (rs.next()) {
                    String schema = rs.getString("TABLE_SCHEM");
                    if (!isSystemSchema(schema)) {
                        schemas.add(schema);
                    }
                }
            }
            return schemas;
        });
    }

    @Override
    public List<TableMetadataResponse> listTables(String schema) {
        return listTablesByType(schema, new String[]{TABLE_TYPE}, TABLE_TYPE);
    }

    @Override
    public List<TableMetadataResponse> listViews(String schema) {
        return listTablesByType(schema, new String[]{VIEW_TYPE}, VIEW_TYPE);
    }

    @Override
    public List<ColumnMetadataResponse> listColumns(String schema, String table) {
        return withMetaData(metaData -> {
            List<ColumnMetadataResponse> columns = new ArrayList<>();
            try (ResultSet rs = metaData.getColumns(null, schema, table, null)) {
                while (rs.next()) {
                    columns.add(ColumnMetadataResponse.builder()
                            .columnName(rs.getString("COLUMN_NAME"))
                            .dataType(rs.getString("TYPE_NAME"))
                            .nullable(rs.getInt("NULLABLE") == DatabaseMetaData.columnNullable)
                            .length(readNullableInt(rs, "COLUMN_SIZE"))
                            .precision(readNullableInt(rs, "COLUMN_SIZE"))
                            .scale(readNullableInt(rs, "DECIMAL_DIGITS"))
                            .defaultValue(rs.getString("COLUMN_DEF"))
                            .ordinalPosition(rs.getInt("ORDINAL_POSITION"))
                            .build());
                }
            }
            return columns;
        });
    }

    @Override
    public PrimaryKeyResponse getPrimaryKey(String schema, String table) {
        return withMetaData(metaData -> {
            String constraintName = null;
            Map<Integer, String> columnsBySequence = new TreeMap<>();
            try (ResultSet rs = metaData.getPrimaryKeys(null, schema, table)) {
                while (rs.next()) {
                    columnsBySequence.put((int) rs.getShort("KEY_SEQ"), rs.getString("COLUMN_NAME"));
                    if (constraintName == null) {
                        constraintName = rs.getString("PK_NAME");
                    }
                }
            }
            if (columnsBySequence.isEmpty()) {
                return null;
            }
            return PrimaryKeyResponse.builder()
                    .constraintName(constraintName)
                    .columnNames(new ArrayList<>(columnsBySequence.values()))
                    .build();
        });
    }

    @Override
    public List<ForeignKeyResponse> listForeignKeys(String schema, String table) {
        return withMetaData(metaData -> {
            Map<String, ForeignKeyBuilder> byName = new LinkedHashMap<>();
            try (ResultSet rs = metaData.getImportedKeys(null, schema, table)) {
                while (rs.next()) {
                    String fkName = rs.getString("FK_NAME");
                    String referencedSchema = rs.getString("PKTABLE_SCHEM");
                    String referencedTable = rs.getString("PKTABLE_NAME");
                    ForeignKeyBuilder builder = byName.computeIfAbsent(fkName,
                            name -> new ForeignKeyBuilder(name, referencedSchema, referencedTable));
                    builder.addColumn((int) rs.getShort("KEY_SEQ"), rs.getString("FKCOLUMN_NAME"),
                            rs.getString("PKCOLUMN_NAME"));
                }
            }
            List<ForeignKeyResponse> foreignKeys = new ArrayList<>();
            for (ForeignKeyBuilder builder : byName.values()) {
                foreignKeys.add(builder.build());
            }
            return foreignKeys;
        });
    }

    @Override
    public List<IndexResponse> listIndexes(String schema, String table) {
        return withMetaData(metaData -> {
            Map<String, IndexBuilder> byName = new LinkedHashMap<>();
            try (ResultSet rs = metaData.getIndexInfo(null, schema, table, false, true)) {
                while (rs.next()) {
                    String indexName = rs.getString("INDEX_NAME");
                    if (indexName == null) {
                        continue;
                    }
                    boolean unique = !rs.getBoolean("NON_UNIQUE");
                    IndexBuilder builder = byName.computeIfAbsent(indexName, name -> new IndexBuilder(name, unique));
                    builder.addColumn((int) rs.getShort("ORDINAL_POSITION"), rs.getString("COLUMN_NAME"));
                }
            }
            List<IndexResponse> indexes = new ArrayList<>();
            for (IndexBuilder builder : byName.values()) {
                indexes.add(builder.build());
            }
            return indexes;
        });
    }

    private List<TableMetadataResponse> listTablesByType(String schema, String[] types, String tableType) {
        return withMetaData(metaData -> {
            List<TableMetadataResponse> tables = new ArrayList<>();
            try (ResultSet rs = metaData.getTables(null, schema, null, types)) {
                while (rs.next()) {
                    tables.add(TableMetadataResponse.builder()
                            .tableName(rs.getString("TABLE_NAME"))
                            .tableType(tableType)
                            .build());
                }
            }
            return tables;
        });
    }

    private boolean isSystemSchema(String schema) {
        if (schema == null) {
            return false;
        }
        String lower = schema.toLowerCase();
        return SYSTEM_SCHEMAS.contains(lower)
                || lower.startsWith(SYSTEM_TEMP_SCHEMA_PREFIX)
                || lower.startsWith(SYSTEM_TOAST_TEMP_SCHEMA_PREFIX);
    }

    private static Integer readNullableInt(ResultSet rs, String column) throws SQLException {
        int value = rs.getInt(column);
        return rs.wasNull() ? null : value;
    }

    private <T> T withMetaData(MetaDataFunction<T> function) {
        try (Connection connection = dataSource.getConnection()) {
            return function.apply(connection.getMetaData());
        } catch (SQLException ex) {
            throw new RuntimeException("Failed to retrieve metadata from the database.", ex);
        }
    }

    @FunctionalInterface
    private interface MetaDataFunction<T> {
        T apply(DatabaseMetaData metaData) throws SQLException;
    }

    private static final class ForeignKeyBuilder {
        private final String name;
        private final String referencedSchema;
        private final String referencedTable;
        private final Map<Integer, String> columns = new TreeMap<>();
        private final Map<Integer, String> referencedColumns = new TreeMap<>();

        private ForeignKeyBuilder(String name, String referencedSchema, String referencedTable) {
            this.name = name;
            this.referencedSchema = referencedSchema;
            this.referencedTable = referencedTable;
        }

        private void addColumn(int keySeq, String columnName, String referencedColumnName) {
            columns.put(keySeq, columnName);
            referencedColumns.put(keySeq, referencedColumnName);
        }

        private ForeignKeyResponse build() {
            return ForeignKeyResponse.builder()
                    .constraintName(name)
                    .columnNames(new ArrayList<>(columns.values()))
                    .referencedSchema(referencedSchema)
                    .referencedTable(referencedTable)
                    .referencedColumnNames(new ArrayList<>(referencedColumns.values()))
                    .build();
        }
    }

    private static final class IndexBuilder {
        private final String name;
        private final boolean unique;
        private final Map<Integer, String> columns = new TreeMap<>();

        private IndexBuilder(String name, boolean unique) {
            this.name = name;
            this.unique = unique;
        }

        private void addColumn(int ordinalPosition, String columnName) {
            columns.put(ordinalPosition, columnName);
        }

        private IndexResponse build() {
            return IndexResponse.builder()
                    .indexName(name)
                    .unique(unique)
                    .columnNames(new ArrayList<>(columns.values()))
                    .build();
        }
    }
}

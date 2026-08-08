package com.querypilot.client;

import com.querypilot.dto.response.QueryExecutionResult;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.ResultSetMetaData;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * PostgreSQL implementation of {@link DatabaseClient}, built on Spring's
 * {@link JdbcTemplate}. Execution failures are left to propagate as
 * {@link org.springframework.dao.DataAccessException} — translating them
 * into a safe, user-facing error is the responsibility of the caller.
 */
@Component
public class PostgresDatabaseClient implements DatabaseClient {

    private final JdbcTemplate jdbcTemplate;

    public PostgresDatabaseClient(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public QueryExecutionResult execute(String sql) {
        return jdbcTemplate.query(sql, rs -> {
            ResultSetMetaData metaData = rs.getMetaData();
            int columnCount = metaData.getColumnCount();

            List<String> columns = new ArrayList<>(columnCount);
            for (int i = 1; i <= columnCount; i++) {
                columns.add(metaData.getColumnLabel(i));
            }

            List<Map<String, Object>> rows = new ArrayList<>();
            while (rs.next()) {
                Map<String, Object> row = new LinkedHashMap<>(columnCount);
                for (int i = 1; i <= columnCount; i++) {
                    row.put(columns.get(i - 1), rs.getObject(i));
                }
                rows.add(row);
            }

            return QueryExecutionResult.builder().columns(columns).rows(rows).build();
        });
    }
}

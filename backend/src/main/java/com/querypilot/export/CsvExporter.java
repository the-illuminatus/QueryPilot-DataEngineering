package com.querypilot.export;

import com.querypilot.dto.response.QueryExecutionResponse;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * Renders a {@link QueryExecutionResponse} as CSV using plain
 * {@link StringBuilder} text formatting — no external CSV library.
 * <p>
 * Deliberately a plain class rather than a Spring bean: it has no
 * dependencies to inject and holds no state between calls, so a
 * {@code @Component} would add nothing.
 */
public class CsvExporter {

    private static final String DELIMITER = ",";
    private static final String LINE_BREAK = "\n";

    public byte[] export(QueryExecutionResponse response) {
        List<String> columns = response.getColumns();
        StringBuilder csv = new StringBuilder();

        appendRow(csv, columns);
        for (Map<String, Object> row : response.getRows()) {
            appendRow(csv, columns.stream().map(column -> formatValue(row.get(column))).toList());
        }

        return csv.toString().getBytes(StandardCharsets.UTF_8);
    }

    private void appendRow(StringBuilder csv, List<String> values) {
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                csv.append(DELIMITER);
            }
            csv.append(escape(values.get(i)));
        }
        csv.append(LINE_BREAK);
    }

    private String formatValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String escape(String value) {
        if (value.contains(DELIMITER) || value.contains("\"") || value.contains(LINE_BREAK) || value.contains("\r")) {
            return "\"" + value.replace("\"", "\"\"") + "\"";
        }
        return value;
    }
}

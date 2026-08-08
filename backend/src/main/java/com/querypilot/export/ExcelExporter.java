package com.querypilot.export;

import com.querypilot.dto.response.QueryExecutionResponse;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.List;
import java.util.Map;

/**
 * Renders a {@link QueryExecutionResponse} as a single-worksheet {@code .xlsx}
 * workbook using Apache POI, with column headers in the first row.
 * <p>
 * Deliberately a plain class rather than a Spring bean: it has no
 * dependencies to inject and holds no state between calls, so a
 * {@code @Component} would add nothing.
 */
public class ExcelExporter {

    private static final String SHEET_NAME = "Results";

    public byte[] export(QueryExecutionResponse response) {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet(SHEET_NAME);
            List<String> columns = response.getColumns();

            writeRow(sheet.createRow(0), columns);

            List<Map<String, Object>> rows = response.getRows();
            for (int i = 0; i < rows.size(); i++) {
                Map<String, Object> row = rows.get(i);
                writeRow(sheet.createRow(i + 1), columns.stream().map(column -> formatValue(row.get(column))).toList());
            }

            workbook.write(out);
            return out.toByteArray();
        } catch (IOException ex) {
            throw new UncheckedIOException("Failed to generate the Excel export.", ex);
        }
    }

    private void writeRow(Row row, List<String> values) {
        for (int i = 0; i < values.size(); i++) {
            row.createCell(i).setCellValue(values.get(i));
        }
    }

    private String formatValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }
}

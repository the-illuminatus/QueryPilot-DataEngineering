package com.querypilot.service.impl;

import com.querypilot.dto.response.QueryExecutionResponse;
import com.querypilot.export.CsvExporter;
import com.querypilot.export.ExcelExporter;
import com.querypilot.service.ExportService;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

/**
 * Default {@link ExportService} implementation. Delegates rendering to
 * {@link CsvExporter}/{@link ExcelExporter} — plain classes it owns directly
 * rather than injects, since neither holds state or has dependencies of its
 * own, matching how {@code PromptServiceImpl} owns {@code PromptBuilder}.
 */
@Service
public class ExportServiceImpl implements ExportService {

    private final CsvExporter csvExporter = new CsvExporter();
    private final ExcelExporter excelExporter = new ExcelExporter();

    @Override
    public Resource exportToCsv(QueryExecutionResponse response) {
        return new ByteArrayResource(csvExporter.export(response));
    }

    @Override
    public Resource exportToExcel(QueryExecutionResponse response) {
        return new ByteArrayResource(excelExporter.export(response));
    }
}

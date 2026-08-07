package com.querypilot.service.impl;

import com.querypilot.dto.request.PromptRequest;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.PromptResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;
import com.querypilot.prompt.PromptBuilder;
import com.querypilot.service.MetadataService;
import com.querypilot.service.PromptService;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Default {@link PromptService} implementation. Retrieves database metadata
 * through {@link MetadataService} and delegates prompt assembly to
 * {@link PromptBuilder} — no AI calls, no SQL generation.
 * <p>
 * {@link MetadataService#getDatabaseMetadata()} only returns table/view
 * names per schema; it does not include columns, primary keys, or foreign
 * keys (those are populated only by the single-table detail endpoint). Since
 * an NL2SQL prompt is useless without column and relationship information,
 * this class enriches each table/view via
 * {@link MetadataService#getTableMetadata(String, String)} before handing
 * the metadata to {@link PromptBuilder}.
 */
@Service
public class PromptServiceImpl implements PromptService {

    private final MetadataService metadataService;
    private final PromptBuilder promptBuilder;

    public PromptServiceImpl(MetadataService metadataService) {
        this.metadataService = metadataService;
        this.promptBuilder = new PromptBuilder();
    }

    @Override
    public PromptResponse buildPrompt(PromptRequest request) {
        MetadataResponse metadata = enrichMetadata(metadataService.getDatabaseMetadata());
        String prompt = promptBuilder.buildPrompt(request.getQuestion(), metadata);
        return PromptResponse.builder().prompt(prompt).build();
    }

    private MetadataResponse enrichMetadata(MetadataResponse shallow) {
        List<SchemaMetadataResponse> enrichedSchemas = shallow.getSchemas().stream()
                .map(this::enrichSchema)
                .toList();

        return MetadataResponse.builder()
                .databaseProductName(shallow.getDatabaseProductName())
                .databaseProductVersion(shallow.getDatabaseProductVersion())
                .schemas(enrichedSchemas)
                .build();
    }

    private SchemaMetadataResponse enrichSchema(SchemaMetadataResponse schema) {
        return SchemaMetadataResponse.builder()
                .schemaName(schema.getSchemaName())
                .tables(enrichTables(schema.getSchemaName(), schema.getTables()))
                .views(enrichTables(schema.getSchemaName(), schema.getViews()))
                .build();
    }

    private List<TableMetadataResponse> enrichTables(String schemaName, List<TableMetadataResponse> tables) {
        return tables.stream()
                .map(table -> metadataService.getTableMetadata(schemaName, table.getTableName()))
                .toList();
    }
}

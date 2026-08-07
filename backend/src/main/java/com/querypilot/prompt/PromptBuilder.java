package com.querypilot.prompt;

import com.querypilot.dto.response.ColumnMetadataResponse;
import com.querypilot.dto.response.ForeignKeyResponse;
import com.querypilot.dto.response.MetadataResponse;
import com.querypilot.dto.response.PrimaryKeyResponse;
import com.querypilot.dto.response.SchemaMetadataResponse;
import com.querypilot.dto.response.TableMetadataResponse;

import java.util.List;

/**
 * Assembles the structured natural-language prompt later sent to Gemini for
 * SQL generation. Pure text formatting over data already retrieved by the
 * caller — never calls an AI model, generates SQL, or reaches into the
 * database itself.
 * <p>
 * Deliberately a plain class rather than a Spring bean: it has no
 * dependencies to inject and holds no state between calls, so a
 * {@code @Component} would add nothing. Callers simply {@code new} one.
 */
public class PromptBuilder {

    private static final String SECTION_DIVIDER = "----------------------------------------";

    public String buildPrompt(String question, MetadataResponse metadata) {
        StringBuilder prompt = new StringBuilder();
        appendSystemSection(prompt);
        appendMetadataSection(prompt, metadata);
        appendQuestionSection(prompt, question);
        appendRulesSection(prompt);
        return prompt.toString();
    }

    private void appendSystemSection(StringBuilder prompt) {
        appendSectionHeader(prompt, "SYSTEM");
        prompt.append("You are an expert PostgreSQL database assistant embedded in QueryPilot, ")
                .append("a natural-language-to-SQL system. Your task is to translate the question ")
                .append("in USER QUESTION into a single PostgreSQL SQL query, using only the schema ")
                .append("described in DATABASE METADATA and following every rule in SQL GENERATION RULES.")
                .append("\n\n");
    }

    private void appendMetadataSection(StringBuilder prompt, MetadataResponse metadata) {
        appendSectionHeader(prompt, "DATABASE METADATA");

        if (metadata == null || metadata.getSchemas().isEmpty()) {
            prompt.append("No database metadata is available.\n\n");
            return;
        }

        prompt.append("Database Product: ")
                .append(metadata.getDatabaseProductName())
                .append(" ")
                .append(metadata.getDatabaseProductVersion())
                .append("\n\n");

        for (SchemaMetadataResponse schema : metadata.getSchemas()) {
            appendSchema(prompt, schema);
        }
    }

    private void appendSchema(StringBuilder prompt, SchemaMetadataResponse schema) {
        prompt.append("Schema: ").append(schema.getSchemaName()).append("\n");

        for (TableMetadataResponse table : schema.getTables()) {
            appendTable(prompt, table);
        }
        for (TableMetadataResponse view : schema.getViews()) {
            appendTable(prompt, view);
        }
        prompt.append("\n");
    }

    private void appendTable(StringBuilder prompt, TableMetadataResponse table) {
        prompt.append("  ").append(table.getTableType()).append(": ").append(table.getTableName()).append("\n");

        for (ColumnMetadataResponse column : table.getColumns()) {
            prompt.append("    - ")
                    .append(column.getColumnName())
                    .append(": ")
                    .append(column.getDataType())
                    .append(column.isNullable() ? " NULL" : " NOT NULL")
                    .append("\n");
        }

        PrimaryKeyResponse primaryKey = table.getPrimaryKey();
        if (primaryKey != null) {
            prompt.append("    Primary Key: ")
                    .append(String.join(", ", primaryKey.getColumnNames()))
                    .append("\n");
        }

        for (ForeignKeyResponse foreignKey : table.getForeignKeys()) {
            prompt.append("    Foreign Key: (")
                    .append(String.join(", ", foreignKey.getColumnNames()))
                    .append(") -> ")
                    .append(foreignKey.getReferencedSchema())
                    .append(".")
                    .append(foreignKey.getReferencedTable())
                    .append("(")
                    .append(String.join(", ", foreignKey.getReferencedColumnNames()))
                    .append(")\n");
        }
    }

    private void appendQuestionSection(StringBuilder prompt, String question) {
        appendSectionHeader(prompt, "USER QUESTION");
        prompt.append(question).append("\n\n");
    }

    private void appendRulesSection(StringBuilder prompt) {
        appendSectionHeader(prompt, "SQL GENERATION RULES");
        List<String> rules = List.of(
                "Generate PostgreSQL SQL only.",
                "Return SQL only — no explanations, no markdown formatting, no commentary.",
                "Never invent tables, columns, or relationships that are not present in DATABASE METADATA.",
                "Use only the schema objects and columns supplied in DATABASE METADATA.",
                "Prefer explicit JOIN ... ON syntax over implicit joins or correlated subqueries."
        );
        for (int i = 0; i < rules.size(); i++) {
            prompt.append(i + 1).append(". ").append(rules.get(i)).append("\n");
        }
    }

    private void appendSectionHeader(StringBuilder prompt, String title) {
        prompt.append(SECTION_DIVIDER).append("\n")
                .append(title).append("\n")
                .append(SECTION_DIVIDER).append("\n");
    }
}

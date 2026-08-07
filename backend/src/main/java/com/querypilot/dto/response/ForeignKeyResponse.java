package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * A foreign key constraint, supporting composite keys — {@code columnNames}
 * and {@code referencedColumnNames} are ordered pairwise by key sequence.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ForeignKeyResponse {

    private String constraintName;
    private List<String> columnNames;
    private String referencedSchema;
    private String referencedTable;
    private List<String> referencedColumnNames;
}

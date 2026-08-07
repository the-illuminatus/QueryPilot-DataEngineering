package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Metadata for a single table or view column.
 * <p>
 * {@code length} and {@code precision} both come from JDBC's
 * {@code COLUMN_SIZE}, which represents different things depending on the
 * column's data type (max character length for text types, numeric
 * precision for numeric types) — both fields are populated with the same
 * value so callers can read whichever name matches the column's type.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ColumnMetadataResponse {

    private String columnName;
    private String dataType;
    private boolean nullable;
    private Integer length;
    private Integer precision;
    private Integer scale;
    private String defaultValue;
    private int ordinalPosition;
}

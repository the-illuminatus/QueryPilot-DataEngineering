package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * A table's primary key constraint. A table has at most one; the columns are
 * ordered per the key sequence reported by the driver, supporting composite
 * keys.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PrimaryKeyResponse {

    private String constraintName;
    private List<String> columnNames;
}

package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * A single index defined on a table, with its columns ordered by ordinal
 * position (supporting multi-column indexes).
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class IndexResponse {

    private String indexName;
    private boolean unique;
    private List<String> columnNames;
}

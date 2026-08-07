package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * The SQL generated for a user's question. Carries only the raw SQL text —
 * it is neither validated nor executed by this sprint.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryResponse {

    private String sql;
}

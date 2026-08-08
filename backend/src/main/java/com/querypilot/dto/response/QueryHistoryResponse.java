package com.querypilot.dto.response;

import com.querypilot.entity.QueryStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * One recorded {@link com.querypilot.entity.QueryHistory} entry, scoped to
 * the requesting user. Omits the owning user's email — the caller already
 * knows it is their own history.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QueryHistoryResponse {

    private Long id;
    private String question;
    private String generatedSql;
    private long executionTimeMs;
    private int rowCount;
    private QueryStatus status;
    private LocalDateTime executedAt;
}

package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * One saved query, scoped to the requesting user. Omits the owning user's
 * email — the caller already knows it is their own.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SavedQueryResponse {

    private Long id;
    private String title;
    private String question;
    private String generatedSql;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}

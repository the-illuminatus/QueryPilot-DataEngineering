package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Health signal for the metadata layer — confirms the configured data
 * source can actually be introspected, not just that the server is up.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MetadataHealthResponse {

    private String status;
    private String databaseProductName;
    private String databaseProductVersion;
}

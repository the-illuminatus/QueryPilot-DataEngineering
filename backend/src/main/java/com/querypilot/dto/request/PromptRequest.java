package com.querypilot.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Payload for building a structured NL2SQL prompt from a natural language
 * question. Carries no database context — the schema is resolved server-side
 * via {@link com.querypilot.service.MetadataService}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PromptRequest {

    @NotBlank(message = "Question is required.")
    private String question;
}

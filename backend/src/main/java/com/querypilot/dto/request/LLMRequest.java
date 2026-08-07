package com.querypilot.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Provider-neutral request passed to {@link com.querypilot.client.LLMClient}.
 * Carries nothing but the fully-assembled prompt text — no provider-specific
 * shape leaks past this point.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LLMRequest {

    private String prompt;
}

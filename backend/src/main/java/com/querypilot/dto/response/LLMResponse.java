package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Provider-neutral response returned by {@link com.querypilot.client.LLMClient}.
 * Holds only the model's generated text — no provider-specific response
 * shape (candidates, safety ratings, usage metadata, ...) escapes the
 * client implementation.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LLMResponse {

    private String content;
}

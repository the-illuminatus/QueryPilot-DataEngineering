package com.querypilot.client;

import com.querypilot.dto.request.LLMRequest;
import com.querypilot.dto.response.LLMResponse;

/**
 * Abstraction over a text-generation LLM provider. Every service depends on
 * this interface, never on a specific vendor's implementation —
 * {@code GeminiClient} is the only implementation today, but additional
 * providers can be added later without touching any caller.
 */
public interface LLMClient {

    LLMResponse generate(LLMRequest request);
}

package com.querypilot.service;

import com.querypilot.dto.request.PromptRequest;
import com.querypilot.dto.response.PromptResponse;

/**
 * Builds structured NL2SQL prompts from a user's natural language question.
 * Composes {@link MetadataService} output with
 * {@link com.querypilot.prompt.PromptBuilder} — never calls an AI model,
 * generates SQL, or persists anything.
 */
public interface PromptService {

    PromptResponse buildPrompt(PromptRequest request);
}

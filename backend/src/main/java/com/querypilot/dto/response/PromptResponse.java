package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * The structured prompt assembled by the Prompt Engine, ready to be sent to
 * an AI model by a future sprint. Contains no SQL — this response is never
 * anything more than prompt text.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PromptResponse {

    private String prompt;
}

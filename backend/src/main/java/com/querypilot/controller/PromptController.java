package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.PromptRequest;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.PromptResponse;
import com.querypilot.service.PromptService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes the Prompt Engine. Holds no business logic — every request is
 * delegated straight to {@link PromptService}. Protected by the existing
 * JWT authentication like every non-{@code /auth} endpoint.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/prompt")
public class PromptController {

    private final PromptService promptService;

    public PromptController(PromptService promptService) {
        this.promptService = promptService;
    }

    @PostMapping("/build")
    public ResponseEntity<ApiResponse<PromptResponse>> build(@Valid @RequestBody PromptRequest request) {
        PromptResponse response = promptService.buildPrompt(request);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.PROMPT_GENERATED_SUCCESS_MESSAGE, response));
    }
}

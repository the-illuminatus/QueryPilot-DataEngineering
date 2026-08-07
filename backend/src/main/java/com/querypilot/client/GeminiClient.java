package com.querypilot.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.querypilot.config.GeminiConfig;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.LLMRequest;
import com.querypilot.dto.response.LLMResponse;
import com.querypilot.exception.LLMException;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.time.Duration;
import java.util.List;

/**
 * Google Gemini implementation of {@link LLMClient}, built on the Gemini
 * {@code generateContent} REST API. Every Gemini-specific detail — the wire
 * request/response shape, the endpoint URL, and quirks like the model
 * wrapping its answer in a markdown code fence — is confined to this class.
 * Nothing outside it ever sees a Gemini type.
 */
@Component
public class GeminiClient implements LLMClient {

    private final GeminiConfig geminiConfig;
    private final RestTemplate restTemplate;

    public GeminiClient(GeminiConfig geminiConfig, RestTemplateBuilder restTemplateBuilder) {
        this.geminiConfig = geminiConfig;
        Duration timeout = Duration.ofMillis(geminiConfig.getTimeout());
        this.restTemplate = restTemplateBuilder
                .setConnectTimeout(timeout)
                .setReadTimeout(timeout)
                .build();
    }

    @Override
    public LLMResponse generate(LLMRequest request) {
        GeminiGenerateContentRequest geminiRequest = GeminiGenerateContentRequest.builder()
                .contents(List.of(GeminiContent.builder()
                        .parts(List.of(GeminiPart.builder().text(request.getPrompt()).build()))
                        .build()))
                .build();

        GeminiGenerateContentResponse geminiResponse = callGemini(geminiRequest);
        String generatedText = extractText(geminiResponse);

        return LLMResponse.builder().content(generatedText).build();
    }

    private GeminiGenerateContentResponse callGemini(GeminiGenerateContentRequest geminiRequest) {
        try {
            return restTemplate.postForObject(buildUrl(), geminiRequest, GeminiGenerateContentResponse.class);
        } catch (ResourceAccessException ex) {
            // Covers both connection failures and read-timeouts.
            throw new LLMException(ApplicationConstants.LLM_TIMEOUT_MESSAGE, ex);
        } catch (RestClientException ex) {
            throw new LLMException(ApplicationConstants.LLM_REQUEST_FAILED_MESSAGE, ex);
        }
    }

    private String buildUrl() {
        return geminiConfig.getEndpoint() + "/" + geminiConfig.getModel()
                + ":generateContent?key=" + geminiConfig.getApiKey();
    }

    private String extractText(GeminiGenerateContentResponse response) {
        if (response == null || response.getCandidates() == null || response.getCandidates().isEmpty()) {
            throw new LLMException(ApplicationConstants.LLM_EMPTY_RESPONSE_MESSAGE);
        }

        GeminiContent content = response.getCandidates().get(0).getContent();
        if (content == null || content.getParts() == null || content.getParts().isEmpty()) {
            throw new LLMException(ApplicationConstants.LLM_EMPTY_RESPONSE_MESSAGE);
        }

        String text = content.getParts().get(0).getText();
        if (text == null || text.isBlank()) {
            throw new LLMException(ApplicationConstants.LLM_EMPTY_RESPONSE_MESSAGE);
        }

        return stripMarkdownFence(text.trim());
    }

    /**
     * Gemini frequently wraps generated SQL in a ```sql ... ``` fence despite
     * being instructed to return SQL only. Stripping it is response-format
     * normalization, not SQL validation — the SQL text itself is never
     * inspected or altered.
     */
    private String stripMarkdownFence(String text) {
        if (!text.startsWith("```")) {
            return text;
        }
        String withoutOpeningFence = text.replaceFirst("^```[a-zA-Z]*\\s*", "");
        int closingFenceIndex = withoutOpeningFence.lastIndexOf("```");
        if (closingFenceIndex >= 0) {
            return withoutOpeningFence.substring(0, closingFenceIndex).trim();
        }
        return withoutOpeningFence.trim();
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    private static class GeminiGenerateContentRequest {
        private List<GeminiContent> contents;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    private static class GeminiContent {
        private List<GeminiPart> parts;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    private static class GeminiPart {
        private String text;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    private static class GeminiGenerateContentResponse {
        private List<GeminiCandidate> candidates;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    private static class GeminiCandidate {
        private GeminiContent content;
    }
}

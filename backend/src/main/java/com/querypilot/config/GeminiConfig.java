package com.querypilot.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Binds Gemini API configuration from {@code application.yml} (prefix
 * {@code gemini}). The API key is never hardcoded — {@code gemini.api-key}
 * must be supplied via the {@code GEMINI_API_KEY} environment variable in
 * every real environment; only local development/test profiles provide a
 * fallback.
 */
@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "gemini")
public class GeminiConfig {

    private String apiKey;
    private String model;
    private String endpoint;
    private long timeout;
}

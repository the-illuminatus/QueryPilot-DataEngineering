package com.querypilot.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Binds JWT signing configuration from {@code application.yml} (prefix
 * {@code jwt}). The secret is never hardcoded — {@code jwt.secret} must be
 * supplied via the {@code JWT_SECRET} environment variable in every real
 * environment; only local development/test profiles provide a fallback.
 */
@Getter
@Setter
@Configuration
@ConfigurationProperties(prefix = "jwt")
public class JwtConfig {

    private String secret;
    private long expiration;
    private String issuer;
}

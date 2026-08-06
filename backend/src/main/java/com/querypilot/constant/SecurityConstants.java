package com.querypilot.constant;

/**
 * Constants related to Spring Security configuration.
 * No authentication or JWT logic is defined here yet — this sprint only
 * establishes the stateless security foundation.
 */
public final class SecurityConstants {

    private SecurityConstants() {
    }

    public static final String AUTHORIZATION_HEADER = "Authorization";
    public static final String BEARER_PREFIX = "Bearer ";

    public static final String[] PUBLIC_ENDPOINTS = {
            "/**"
    };
}

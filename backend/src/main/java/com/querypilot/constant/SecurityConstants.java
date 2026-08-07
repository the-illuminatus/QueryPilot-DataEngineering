package com.querypilot.constant;

/**
 * Constants related to Spring Security configuration.
 */
public final class SecurityConstants {

    private SecurityConstants() {
    }

    public static final String AUTHORIZATION_HEADER = "Authorization";
    public static final String BEARER_PREFIX = "Bearer ";
    public static final String BEARER_TOKEN_TYPE = "Bearer";

    public static final String[] PUBLIC_ENDPOINTS = {
            ApiConstants.API_BASE_PATH + "/auth/**"
    };
}

package com.querypilot.constant;

/**
 * Constants related to API structure and versioning.
 */
public final class ApiConstants {

    private ApiConstants() {
    }

    public static final String API_VERSION = "v1";
    public static final String API_BASE_PATH = "/api/" + API_VERSION;

    public static final String CONTENT_TYPE_JSON = "application/json";
}

package com.querypilot.constant;

/**
 * Application-wide constant values shared across layers.
 */
public final class ApplicationConstants {

    private ApplicationConstants() {
    }

    public static final String APPLICATION_NAME = "QueryPilot";

    // Generic response messages
    public static final String GENERIC_SUCCESS_MESSAGE = "Request processed successfully.";
    public static final String GENERIC_ERROR_MESSAGE = "An unexpected error occurred. Please contact support if the issue persists.";
    public static final String VALIDATION_FAILED_MESSAGE = "Validation failed for the provided input.";
    public static final String RESOURCE_NOT_FOUND_MESSAGE = "The requested resource could not be found.";
    public static final String UNAUTHORIZED_MESSAGE = "You are not authorized to perform this action.";
    public static final String ACCESS_DENIED_MESSAGE = "Access to this resource is denied.";
    public static final String BAD_REQUEST_MESSAGE = "The request could not be processed due to invalid input.";

    // Formatting
    public static final String DEFAULT_DATE_TIME_PATTERN = "yyyy-MM-dd'T'HH:mm:ss";
    public static final String DEFAULT_DATE_PATTERN = "yyyy-MM-dd";

    // User domain messages
    public static final String EMAIL_ALREADY_EXISTS_MESSAGE = "An account with this email already exists.";
    public static final String USERNAME_ALREADY_EXISTS_MESSAGE = "This username is already taken.";
    public static final String USER_NOT_FOUND_MESSAGE = "No account exists for the given email.";

    // Authentication flow messages
    public static final String REGISTRATION_SUCCESS_MESSAGE = "User registered successfully.";
    public static final String LOGIN_SUCCESS_MESSAGE = "User logged in successfully.";
    public static final String INVALID_CREDENTIALS_MESSAGE = "Invalid email or password.";

    // Metadata domain messages
    public static final String SCHEMA_NOT_FOUND_MESSAGE = "The requested schema could not be found.";
    public static final String TABLE_NOT_FOUND_MESSAGE = "The requested table could not be found.";

    // Prompt domain messages
    public static final String PROMPT_GENERATED_SUCCESS_MESSAGE = "Prompt generated successfully.";

    // Query / LLM domain messages
    public static final String SQL_GENERATED_SUCCESS_MESSAGE = "SQL generated successfully.";
    public static final String LLM_TIMEOUT_MESSAGE = "The AI model did not respond in time. Please try again.";
    public static final String LLM_REQUEST_FAILED_MESSAGE = "The AI model request failed. Please try again later.";
    public static final String LLM_EMPTY_RESPONSE_MESSAGE = "The AI model returned an empty response. Please try again.";
}

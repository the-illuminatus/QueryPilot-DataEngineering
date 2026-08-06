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
}

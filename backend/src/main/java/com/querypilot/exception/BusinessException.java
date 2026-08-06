package com.querypilot.exception;

/**
 * Thrown when a business rule is violated during request processing.
 */
public class BusinessException extends RuntimeException {

    public BusinessException(String message) {
        super(message);
    }

    public BusinessException(String message, Throwable cause) {
        super(message, cause);
    }
}

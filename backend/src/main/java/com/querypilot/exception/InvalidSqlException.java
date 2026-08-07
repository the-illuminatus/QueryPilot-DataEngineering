package com.querypilot.exception;

/**
 * Thrown by {@link com.querypilot.validator.SQLValidator} when generated SQL
 * is not safe to execute — not read-only, not a single statement, contains
 * comments, or is empty.
 */
public class InvalidSqlException extends RuntimeException {

    public InvalidSqlException(String message) {
        super(message);
    }

    public InvalidSqlException(String message, Throwable cause) {
        super(message, cause);
    }
}

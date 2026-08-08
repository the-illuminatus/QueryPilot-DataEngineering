package com.querypilot.exception;

/**
 * Thrown when validated SQL fails to execute against the database — a
 * missing table or column, an unavailable database, a dropped connection, or
 * a query timeout. The message is always a safe, generic one authored by the
 * throwing service, never the database's raw error text.
 */
public class QueryExecutionException extends RuntimeException {

    public QueryExecutionException(String message) {
        super(message);
    }

    public QueryExecutionException(String message, Throwable cause) {
        super(message, cause);
    }
}

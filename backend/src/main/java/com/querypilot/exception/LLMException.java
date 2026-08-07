package com.querypilot.exception;

/**
 * Thrown when an LLM provider call fails — network failure, timeout, an
 * error response, or an empty/unusable generation. The message is always
 * authored by the throwing client (never the provider's raw error body), so
 * it is always safe to surface to the caller.
 */
public class LLMException extends RuntimeException {

    public LLMException(String message) {
        super(message);
    }

    public LLMException(String message, Throwable cause) {
        super(message, cause);
    }
}

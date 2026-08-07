package com.querypilot.validator;

/**
 * Determines whether generated SQL is safe to execute — nothing more. A
 * validator never executes, modifies, rewrites, or optimizes the SQL it is
 * given; it only accepts it silently or rejects it by throwing.
 */
public interface SQLValidator {

    /**
     * @param sql the raw SQL text to validate, unmodified
     * @throws com.querypilot.exception.InvalidSqlException if the SQL is
     *                                                       empty, not a
     *                                                       single read-only
     *                                                       {@code SELECT}
     *                                                       statement, or
     *                                                       otherwise unsafe
     */
    void validate(String sql);
}

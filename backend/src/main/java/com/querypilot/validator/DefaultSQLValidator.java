package com.querypilot.validator;

import com.querypilot.constant.ApplicationConstants;
import com.querypilot.exception.InvalidSqlException;
import org.springframework.stereotype.Component;

import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Keyword- and shape-based {@link SQLValidator}. Deliberately not backed by
 * a SQL parser — it only ever accepts unmodified input or rejects it, and
 * never inspects structure beyond what a handful of string checks require.
 * <p>
 * Because there is no real parser, checks that key off the literal
 * characters {@code ;}, {@code --}, and {@code /*} can be tripped by those
 * characters appearing inside a string literal rather than as SQL syntax.
 * That is an accepted trade-off: the failure mode is rejecting SQL that was
 * actually safe, never accepting SQL that was actually unsafe.
 */
@Component
public class DefaultSQLValidator implements SQLValidator {

    private static final String SELECT_KEYWORD = "SELECT";

    private static final Set<String> BLOCKED_KEYWORDS = Set.of(
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
            "CREATE", "MERGE", "CALL", "EXEC", "GRANT", "REVOKE");

    private static final Pattern FIRST_KEYWORD_PATTERN = Pattern.compile("^\\s*(\\w+)");

    private static final Pattern BLOCKED_KEYWORD_PATTERN = Pattern.compile(
            "\\b(" + String.join("|", BLOCKED_KEYWORDS) + ")\\b", Pattern.CASE_INSENSITIVE);

    @Override
    public void validate(String sql) {
        if (sql == null || sql.isBlank()) {
            throw new InvalidSqlException(ApplicationConstants.SQL_EMPTY_MESSAGE);
        }

        if (sql.contains("--") || sql.contains("/*") || sql.contains("*/")) {
            throw new InvalidSqlException(ApplicationConstants.SQL_COMMENTS_NOT_ALLOWED_MESSAGE);
        }

        rejectMultipleStatements(sql);

        String firstKeyword = extractFirstKeyword(sql);
        if (!SELECT_KEYWORD.equalsIgnoreCase(firstKeyword)) {
            throw new InvalidSqlException(ApplicationConstants.SQL_ONLY_SELECT_ALLOWED_MESSAGE);
        }

        Matcher blockedMatcher = BLOCKED_KEYWORD_PATTERN.matcher(sql);
        if (blockedMatcher.find()) {
            throw new InvalidSqlException(ApplicationConstants.SQL_ONLY_SELECT_ALLOWED_MESSAGE);
        }
    }

    private void rejectMultipleStatements(String sql) {
        String trimmed = sql.trim();
        if (trimmed.endsWith(";")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1).trim();
        }
        if (trimmed.isEmpty()) {
            throw new InvalidSqlException(ApplicationConstants.SQL_EMPTY_MESSAGE);
        }
        if (trimmed.contains(";")) {
            throw new InvalidSqlException(ApplicationConstants.SQL_MULTIPLE_STATEMENTS_MESSAGE);
        }
    }

    private String extractFirstKeyword(String sql) {
        Matcher matcher = FIRST_KEYWORD_PATTERN.matcher(sql);
        return matcher.find() ? matcher.group(1) : "";
    }
}

package com.querypilot.util;

import com.querypilot.constant.ApplicationConstants;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Reusable helpers for formatting and parsing {@link LocalDateTime} values.
 */
public final class DateTimeUtil {

    private static final DateTimeFormatter DEFAULT_FORMATTER =
            DateTimeFormatter.ofPattern(ApplicationConstants.DEFAULT_DATE_TIME_PATTERN);

    private DateTimeUtil() {
    }

    public static String format(LocalDateTime dateTime) {
        return dateTime == null ? null : dateTime.format(DEFAULT_FORMATTER);
    }

    public static LocalDateTime parse(String dateTime) {
        return dateTime == null || dateTime.isBlank() ? null : LocalDateTime.parse(dateTime, DEFAULT_FORMATTER);
    }

    public static LocalDateTime now() {
        return LocalDateTime.now();
    }
}

package com.querypilot.constant;

/**
 * Constants related to API structure and versioning.
 */
public final class ApiConstants {

    private ApiConstants() {
    }

    public static final String API_VERSION = "v1";
    public static final String API_BASE_PATH = "/api/" + API_VERSION;

    public static final String CONTENT_TYPE_CSV = "text/csv";
    public static final String CONTENT_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    public static final String CSV_EXPORT_FILENAME = "query-results.csv";
    public static final String XLSX_EXPORT_FILENAME = "query-results.xlsx";
}

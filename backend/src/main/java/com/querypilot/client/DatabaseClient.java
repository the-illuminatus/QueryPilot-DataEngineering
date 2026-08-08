package com.querypilot.client;

import com.querypilot.dto.response.QueryExecutionResult;

/**
 * Abstraction over the execution boundary between the application and a
 * database. The rest of the application depends on this interface, never on
 * a specific vendor's implementation — {@code PostgresDatabaseClient} is the
 * only implementation today, but additional database vendors (MySQL, SQL
 * Server, Oracle, Redshift, Snowflake, etc.) can be added later without
 * touching any caller.
 * <p>
 * A {@code DatabaseClient} only executes SQL and returns what the database
 * returned. It never validates SQL, never generates SQL, and never contains
 * business logic — the caller is responsible for passing SQL that has
 * already been validated.
 */
public interface DatabaseClient {

    QueryExecutionResult execute(String sql);
}

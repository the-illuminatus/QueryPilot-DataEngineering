package com.querypilot.entity;

/**
 * Authorization role assigned to a {@link User}. Single-role model only —
 * no permission granularity beyond this is in scope.
 */
public enum Role {
    USER,
    ADMIN
}

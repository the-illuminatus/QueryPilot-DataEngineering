package com.querypilot.entity;

/**
 * Identity source a {@link User} account originates from. Only {@code LOCAL}
 * is actually issued today; the OAuth values are reserved for a future
 * sprint and carry no implementation yet.
 */
public enum AuthenticationProvider {
    LOCAL,
    GOOGLE,
    MICROSOFT,
    GITHUB
}

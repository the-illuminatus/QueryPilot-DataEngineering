package com.querypilot.service;

import io.jsonwebtoken.Claims;

import java.util.Date;

/**
 * Issues and inspects HS256-signed JWT access tokens. Carries no dependency
 * on the domain model — callers pass the subject and role explicitly.
 */
public interface JwtService {

    /**
     * Builds a signed access token for the given principal.
     *
     * @param subject the token's {@code sub} claim (the user's email)
     * @param role    the token's {@code role} claim (e.g. {@code "USER"})
     */
    String generateToken(String subject, String role);

    /**
     * @return {@code true} only if the token is well-formed, signed with the
     * configured key, issued by the configured issuer, and not expired.
     */
    boolean validateToken(String token);

    String extractUsername(String token);

    Date extractExpiration(String token);

    Claims extractClaims(String token);
}

package com.querypilot.service.impl;

import com.querypilot.config.JwtConfig;
import com.querypilot.service.JwtService;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * Default {@link JwtService} implementation. Tokens are signed with HS256
 * using a {@link SecretKey} derived once from the configured secret via
 * {@link Keys#hmacShaKeyFor} — the raw secret string is never passed to the
 * signer directly.
 */
@Service
public class JwtServiceImpl implements JwtService {

    private static final String ROLE_CLAIM = "role";

    private final JwtConfig jwtConfig;
    private final SecretKey signingKey;

    public JwtServiceImpl(JwtConfig jwtConfig) {
        this.jwtConfig = jwtConfig;
        this.signingKey = Keys.hmacShaKeyFor(jwtConfig.getSecret().getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public String generateToken(String subject, String role) {
        Date issuedAt = new Date();
        Date expiration = new Date(issuedAt.getTime() + jwtConfig.getExpiration());

        return Jwts.builder()
                .subject(subject)
                .claim(ROLE_CLAIM, role)
                .issuedAt(issuedAt)
                .expiration(expiration)
                .issuer(jwtConfig.getIssuer())
                .signWith(signingKey, Jwts.SIG.HS256)
                .compact();
    }

    @Override
    public boolean validateToken(String token) {
        try {
            extractClaims(token);
            return true;
        } catch (JwtException | IllegalArgumentException ex) {
            return false;
        }
    }

    @Override
    public String extractUsername(String token) {
        return extractClaims(token).getSubject();
    }

    @Override
    public Date extractExpiration(String token) {
        return extractClaims(token).getExpiration();
    }

    @Override
    public Claims extractClaims(String token) {
        return Jwts.parser()
                .verifyWith(signingKey)
                .requireIssuer(jwtConfig.getIssuer())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }
}

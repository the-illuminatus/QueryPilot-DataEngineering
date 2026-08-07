package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * JWT access token issued after successful authentication. Carries no
 * profile data or refresh token — only what the client needs to authorize
 * subsequent requests.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginResponse {

    private String tokenType;
    private String accessToken;
}

package com.querypilot.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Public-facing representation of an authenticated user.
 * <p>
 * Defined as part of the authentication domain foundation; deliberately
 * carries no token/session data since login is not implemented yet.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginResponse {

    private Long id;
    private String username;
    private String email;
    private String firstName;
    private String lastName;
}

package com.querypilot.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Payload for authenticating an existing user.
 * <p>
 * Defined as part of the authentication domain foundation; no login flow
 * consumes it yet.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class LoginRequest {

    @NotBlank(message = "Email is required.")
    @Email(message = "Email must be a valid email address.")
    private String email;

    @NotBlank(message = "Password is required.")
    private String password;
}

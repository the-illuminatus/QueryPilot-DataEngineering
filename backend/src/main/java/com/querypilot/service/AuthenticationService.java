package com.querypilot.service;

import com.querypilot.dto.request.LoginRequest;
import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.LoginResponse;
import com.querypilot.dto.response.RegisterResponse;

/**
 * Orchestrates the authentication flow (registration and login). Login
 * issues a JWT access token via {@link JwtService} on success.
 */
public interface AuthenticationService {

    RegisterResponse register(RegisterRequest request);

    LoginResponse login(LoginRequest request);
}

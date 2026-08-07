package com.querypilot.service.impl;

import com.querypilot.constant.SecurityConstants;
import com.querypilot.dto.request.LoginRequest;
import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.LoginResponse;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.security.CustomUserDetails;
import com.querypilot.service.AuthenticationService;
import com.querypilot.service.JwtService;
import com.querypilot.service.UserService;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

/**
 * Default {@link AuthenticationService} implementation.
 * <p>
 * Registration delegates entirely to {@link UserService}, which already owns
 * uniqueness checks, password encoding, and persistence — no logic is
 * duplicated here. Login delegates credential verification to Spring
 * Security's {@link AuthenticationManager} and, on success, issues a JWT
 * access token via {@link JwtService} — no session or refresh token.
 */
@Service
public class AuthenticationServiceImpl implements AuthenticationService {

    private final UserService userService;
    private final AuthenticationManager authenticationManager;
    private final JwtService jwtService;

    public AuthenticationServiceImpl(UserService userService,
                                      AuthenticationManager authenticationManager,
                                      JwtService jwtService) {
        this.userService = userService;
        this.authenticationManager = authenticationManager;
        this.jwtService = jwtService;
    }

    @Override
    public RegisterResponse register(RegisterRequest request) {
        return userService.register(request);
    }

    @Override
    public LoginResponse login(LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.getEmail(), request.getPassword()));

        SecurityContextHolder.getContext().setAuthentication(authentication);

        CustomUserDetails userDetails = (CustomUserDetails) authentication.getPrincipal();
        String accessToken = jwtService.generateToken(userDetails.getUsername(), userDetails.getUser().getRole().name());

        return LoginResponse.builder()
                .tokenType(SecurityConstants.BEARER_TOKEN_TYPE)
                .accessToken(accessToken)
                .build();
    }
}

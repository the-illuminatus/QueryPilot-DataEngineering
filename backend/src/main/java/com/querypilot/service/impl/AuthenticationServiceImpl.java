package com.querypilot.service.impl;

import com.querypilot.dto.request.LoginRequest;
import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.LoginResponse;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.mapper.UserMapper;
import com.querypilot.security.CustomUserDetails;
import com.querypilot.service.AuthenticationService;
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
 * Security's {@link AuthenticationManager}; no token is issued.
 */
@Service
public class AuthenticationServiceImpl implements AuthenticationService {

    private final UserService userService;
    private final AuthenticationManager authenticationManager;

    public AuthenticationServiceImpl(UserService userService, AuthenticationManager authenticationManager) {
        this.userService = userService;
        this.authenticationManager = authenticationManager;
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
        return UserMapper.toLoginResponse(userDetails.getUser());
    }
}

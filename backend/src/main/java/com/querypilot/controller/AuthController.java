package com.querypilot.controller;

import com.querypilot.constant.ApiConstants;
import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.LoginRequest;
import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.ApiResponse;
import com.querypilot.dto.response.LoginResponse;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.service.AuthenticationService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes the authentication flow. Holds no business logic — every request
 * is delegated straight to {@link AuthenticationService}.
 */
@RestController
@RequestMapping(ApiConstants.API_BASE_PATH + "/auth")
public class AuthController {

    private final AuthenticationService authenticationService;

    public AuthController(AuthenticationService authenticationService) {
        this.authenticationService = authenticationService;
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<RegisterResponse>> register(@Valid @RequestBody RegisterRequest request) {
        RegisterResponse response = authenticationService.register(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(ApplicationConstants.REGISTRATION_SUCCESS_MESSAGE, response));
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<LoginResponse>> login(@Valid @RequestBody LoginRequest request) {
        LoginResponse response = authenticationService.login(request);
        return ResponseEntity.ok(ApiResponse.success(ApplicationConstants.LOGIN_SUCCESS_MESSAGE, response));
    }
}

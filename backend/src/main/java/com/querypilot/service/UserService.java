package com.querypilot.service;

import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.entity.User;

import java.util.Optional;

/**
 * Domain operations for {@link User}. Deliberately excludes authentication
 * concerns (login, token issuance) — those belong to a later sprint.
 */
public interface UserService {

    /**
     * Registers a new user, enforcing uniqueness on email and username and
     * encoding the raw password before persistence.
     */
    RegisterResponse register(RegisterRequest request);

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    boolean existsByUsername(String username);
}

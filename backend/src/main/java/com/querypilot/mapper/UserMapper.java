package com.querypilot.mapper;

import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.entity.User;

/**
 * Converts between {@link User} and its authentication DTOs. Stateless by
 * design — no external mapping library is used.
 */
public final class UserMapper {

    private UserMapper() {
    }

    /**
     * Builds a new {@link User} from a registration request.
     *
     * @param request         the incoming registration payload
     * @param encodedPassword the already BCrypt-encoded password; this mapper
     *                        never handles raw passwords or encoding itself
     */
    public static User toEntity(RegisterRequest request, String encodedPassword) {
        return User.builder()
                .username(request.getUsername())
                .email(request.getEmail())
                .password(encodedPassword)
                .firstName(request.getFirstName())
                .lastName(request.getLastName())
                .active(true)
                .build();
    }

    public static RegisterResponse toRegisterResponse(User user) {
        return RegisterResponse.builder()
                .id(user.getId())
                .username(user.getUsername())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .createdAt(user.getCreatedAt())
                .build();
    }
}

package com.querypilot.service.impl;

import com.querypilot.constant.ApplicationConstants;
import com.querypilot.dto.request.RegisterRequest;
import com.querypilot.dto.response.RegisterResponse;
import com.querypilot.entity.User;
import com.querypilot.exception.BusinessException;
import com.querypilot.mapper.UserMapper;
import com.querypilot.repository.UserRepository;
import com.querypilot.service.UserService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Optional;

/**
 * Default {@link UserService} implementation. Handles persistence and
 * password encoding for the authentication domain foundation only.
 */
@Service
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public UserServiceImpl(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public RegisterResponse register(RegisterRequest request) {
        if (existsByEmail(request.getEmail())) {
            throw new BusinessException(ApplicationConstants.EMAIL_ALREADY_EXISTS_MESSAGE);
        }
        if (existsByUsername(request.getUsername())) {
            throw new BusinessException(ApplicationConstants.USERNAME_ALREADY_EXISTS_MESSAGE);
        }

        String encodedPassword = passwordEncoder.encode(request.getPassword());
        User user = UserMapper.toEntity(request, encodedPassword);
        User savedUser = userRepository.save(user);

        return UserMapper.toRegisterResponse(savedUser);
    }

    @Override
    public Optional<User> findByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    @Override
    public boolean existsByEmail(String email) {
        return userRepository.existsByEmail(email);
    }

    @Override
    public boolean existsByUsername(String username) {
        return userRepository.existsByUsername(username);
    }
}

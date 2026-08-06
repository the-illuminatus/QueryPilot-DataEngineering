package com.querypilot.security;

import com.querypilot.constant.ApplicationConstants;
import com.querypilot.entity.User;
import com.querypilot.repository.UserRepository;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

/**
 * Loads the Spring Security principal for a user by email — the identifier
 * used at login. Reuses {@link UserRepository}; no separate query logic.
 * <p>
 * Throws {@link UsernameNotFoundException} — not a domain
 * {@code ResourceNotFoundException} — so that Spring Security's
 * {@code DaoAuthenticationProvider} folds a missing account into the same
 * generic bad-credentials outcome as a wrong password, preventing user
 * enumeration via the login endpoint.
 */
@Service
public class CustomUserDetailsService implements UserDetailsService {

    private final UserRepository userRepository;

    public CustomUserDetailsService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public UserDetails loadUserByUsername(String email) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException(ApplicationConstants.USER_NOT_FOUND_MESSAGE));
        return new CustomUserDetails(user);
    }
}

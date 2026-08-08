package com.querypilot.repository;

import com.querypilot.entity.SavedQuery;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * Persistence access for {@link SavedQuery}.
 */
public interface SavedQueryRepository extends JpaRepository<SavedQuery, Long> {

    List<SavedQuery> findByUserEmailOrderByUpdatedAtDesc(String userEmail);

    boolean existsByUserEmailAndTitle(String userEmail, String title);
}

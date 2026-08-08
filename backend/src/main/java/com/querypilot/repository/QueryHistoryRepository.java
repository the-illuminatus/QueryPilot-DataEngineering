package com.querypilot.repository;

import com.querypilot.entity.QueryHistory;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

/**
 * Persistence access for {@link QueryHistory}.
 */
public interface QueryHistoryRepository extends JpaRepository<QueryHistory, Long> {

    List<QueryHistory> findByUserEmailOrderByExecutedAtDesc(String userEmail);
}

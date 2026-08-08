package com.querypilot.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Payload for renaming a saved query via {@code PUT /api/v1/saved-queries/{id}}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpdateSavedQueryRequest {

    @NotBlank(message = "Title is required.")
    @Size(max = 100, message = "Title must not exceed 100 characters.")
    private String title;
}

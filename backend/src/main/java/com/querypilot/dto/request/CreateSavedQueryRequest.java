package com.querypilot.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Payload for saving a query via {@code POST /api/v1/saved-queries}.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateSavedQueryRequest {

    @NotBlank(message = "Title is required.")
    @Size(max = 100, message = "Title must not exceed 100 characters.")
    private String title;

    @NotBlank(message = "Question is required.")
    private String question;

    @NotBlank(message = "Generated SQL is required.")
    private String generatedSql;
}

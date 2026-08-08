import { HttpErrorResponse } from '@angular/common/http';

import { ApiResponse } from '../models/api-response.model';

const DEFAULT_ERROR_MESSAGE = 'Something went wrong. Please try again.';

/**
 * Extracts a user-facing message from a failed request against the
 * QueryPilot API. Field-level validation errors (`data` as a field->message
 * map) are flattened into a single readable string.
 */
export function extractErrorMessage(error: HttpErrorResponse): string {
  const body = error.error as ApiResponse<unknown> | undefined;
  if (!body) {
    return DEFAULT_ERROR_MESSAGE;
  }

  if (body.data && typeof body.data === 'object') {
    const fieldMessages = Object.values(body.data as Record<string, string>);
    if (fieldMessages.length > 0) {
      return fieldMessages.join(' ');
    }
  }

  return body.message ?? DEFAULT_ERROR_MESSAGE;
}

/**
 * Standard response envelope returned by every QueryPilot REST API.
 * Mirrors the backend's `ApiResponse<T>` exactly.
 */
export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  timestamp: string;
}

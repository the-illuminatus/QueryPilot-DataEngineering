/** Payload for `POST /api/v1/auth/login`. */
export interface LoginRequest {
  email: string;
  password: string;
}

/** Payload for `POST /api/v1/auth/register`. */
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

/** JWT access token issued after successful authentication. */
export interface LoginResponse {
  tokenType: string;
  accessToken: string;
}

/** Public-facing representation of a newly registered user. */
export interface RegisterResponse {
  id: number;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}

/** Claims decoded from the JWT access token, used for the in-session user identity. */
export interface AuthUser {
  email: string;
  role: string;
  expiresAt: number;
}

/**
 * Decodes the payload of a JWT without verifying its signature. Verification
 * is the backend's responsibility — the frontend only reads claims to drive
 * UI state (e.g. session expiry) and never trusts them for authorization.
 */
export function decodeJwtPayload<T>(token: string): T | null {
  const payload = token.split('.')[1];
  if (!payload) {
    return null;
  }

  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map(char => '%' + char.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    );
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}

export function isJwtExpired(expiresAtSeconds: number): boolean {
  return Date.now() >= expiresAtSeconds * 1000;
}

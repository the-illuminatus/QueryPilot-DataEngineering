import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AuthService } from '../services/auth.service';

const SKIPPED_URL_SEGMENTS = ['/auth/login', '/auth/register'];

/** Attaches the JWT bearer token to every outgoing request except login/register. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const isAuthRequest = SKIPPED_URL_SEGMENTS.some(segment => req.url.includes(segment));
  if (isAuthRequest) {
    return next(req);
  }

  const token = inject(AuthService).getToken();
  if (!token) {
    return next(req);
  }

  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};

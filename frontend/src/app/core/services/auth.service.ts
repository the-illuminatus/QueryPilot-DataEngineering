import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, map, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api-response.model';
import { AuthUser, LoginRequest, LoginResponse, RegisterRequest, RegisterResponse } from '../../shared/models/auth.model';
import { decodeJwtPayload, isJwtExpired } from '../../shared/utils/jwt.util';

interface JwtClaims {
  sub: string;
  role: string;
  exp: number;
}

const TOKEN_STORAGE_KEY = 'qp_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly authBaseUrl = `${environment.apiBaseUrl}/v1/auth`;

  private readonly currentUserSignal = signal<AuthUser | null>(this.readUserFromStorage());
  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.currentUserSignal() !== null);

  login(request: LoginRequest): Observable<LoginResponse> {
    return this.http.post<ApiResponse<LoginResponse>>(`${this.authBaseUrl}/login`, request).pipe(
      map(response => response.data),
      tap(data => this.startSession(data.accessToken))
    );
  }

  register(request: RegisterRequest): Observable<RegisterResponse> {
    return this.http
      .post<ApiResponse<RegisterResponse>>(`${this.authBaseUrl}/register`, request)
      .pipe(map(response => response.data));
  }

  logout(): void {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    this.currentUserSignal.set(null);
    this.router.navigate(['/login']);
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  }

  private startSession(accessToken: string): void {
    localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
    this.currentUserSignal.set(this.toAuthUser(accessToken));
  }

  private readUserFromStorage(): AuthUser | null {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      return null;
    }

    const user = this.toAuthUser(token);
    if (!user) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
    return user;
  }

  private toAuthUser(token: string): AuthUser | null {
    const claims = decodeJwtPayload<JwtClaims>(token);
    if (!claims || isJwtExpired(claims.exp)) {
      return null;
    }

    return { email: claims.sub, role: claims.role, expiresAt: claims.exp };
  }
}

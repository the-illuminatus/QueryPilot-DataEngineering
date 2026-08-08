import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api-response.model';
import { SavedQueryResponse, UpdateSavedQueryRequest } from '../../shared/models/saved-query.model';

@Injectable({ providedIn: 'root' })
export class SavedQueryService {
  private readonly http = inject(HttpClient);
  private readonly savedQueriesBaseUrl = `${environment.apiBaseUrl}/v1/saved-queries`;

  getSavedQueries(): Observable<SavedQueryResponse[]> {
    return this.http
      .get<ApiResponse<SavedQueryResponse[]>>(this.savedQueriesBaseUrl)
      .pipe(map(response => response.data));
  }

  getSavedQuery(id: number): Observable<SavedQueryResponse> {
    return this.http
      .get<ApiResponse<SavedQueryResponse>>(`${this.savedQueriesBaseUrl}/${id}`)
      .pipe(map(response => response.data));
  }

  renameSavedQuery(id: number, title: string): Observable<SavedQueryResponse> {
    const request: UpdateSavedQueryRequest = { title };
    return this.http
      .put<ApiResponse<SavedQueryResponse>>(`${this.savedQueriesBaseUrl}/${id}`, request)
      .pipe(map(response => response.data));
  }

  deleteSavedQuery(id: number): Observable<void> {
    return this.http.delete<ApiResponse<void>>(`${this.savedQueriesBaseUrl}/${id}`).pipe(map(() => undefined));
  }
}

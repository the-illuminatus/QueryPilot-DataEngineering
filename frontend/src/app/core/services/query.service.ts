import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, from, map, switchMap, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api-response.model';
import { QueryExecutionResult, QueryRequest } from '../../shared/models/query.model';
import { CreateSavedQueryRequest, SavedQueryResponse } from '../../shared/models/saved-query.model';

type ExportKind = 'csv' | 'excel';

@Injectable({ providedIn: 'root' })
export class QueryService {
  private readonly http = inject(HttpClient);
  private readonly queryBaseUrl = `${environment.apiBaseUrl}/v1/query`;
  private readonly savedQueriesBaseUrl = `${environment.apiBaseUrl}/v1/saved-queries`;

  generateQuery(question: string): Observable<QueryExecutionResult> {
    const request: QueryRequest = { question };
    return this.http
      .post<ApiResponse<QueryExecutionResult>>(`${this.queryBaseUrl}/generate`, request)
      .pipe(map(response => response.data));
  }

  exportCsv(question: string): Observable<Blob> {
    return this.exportFile('csv', question);
  }

  exportExcel(question: string): Observable<Blob> {
    return this.exportFile('excel', question);
  }

  saveQuery(request: CreateSavedQueryRequest): Observable<SavedQueryResponse> {
    return this.http
      .post<ApiResponse<SavedQueryResponse>>(this.savedQueriesBaseUrl, request)
      .pipe(map(response => response.data));
  }

  private exportFile(kind: ExportKind, question: string): Observable<Blob> {
    const request: QueryRequest = { question };
    return this.http
      .post(`${this.queryBaseUrl}/export/${kind}`, request, { responseType: 'blob' })
      .pipe(catchError(error => this.normalizeBlobError(error)));
  }

  /**
   * Export endpoints return a raw file on success but the same
   * `ApiResponse<void>` JSON envelope as every other endpoint on failure.
   * Because the request was made with `responseType: 'blob'`, Angular hands
   * that JSON error body back as an unparsed `Blob` — re-read it as text and
   * rebuild a normal `HttpErrorResponse` so `extractErrorMessage` keeps working.
   */
  private normalizeBlobError(error: HttpErrorResponse): Observable<never> {
    if (!(error.error instanceof Blob)) {
      return throwError(() => error);
    }

    return from((error.error as Blob).text()).pipe(
      switchMap(text => {
        let parsedBody: unknown = null;
        try {
          parsedBody = JSON.parse(text);
        } catch {
          parsedBody = null;
        }

        return throwError(
          () =>
            new HttpErrorResponse({
              error: parsedBody,
              status: error.status,
              statusText: error.statusText,
              url: error.url ?? undefined
            })
        );
      })
    );
  }
}

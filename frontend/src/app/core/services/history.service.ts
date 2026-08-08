import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api-response.model';
import { QueryHistoryEntry } from '../../shared/models/history.model';

@Injectable({ providedIn: 'root' })
export class HistoryService {
  private readonly http = inject(HttpClient);
  private readonly historyBaseUrl = `${environment.apiBaseUrl}/v1/history`;

  getHistory(): Observable<QueryHistoryEntry[]> {
    return this.http
      .get<ApiResponse<QueryHistoryEntry[]>>(this.historyBaseUrl)
      .pipe(map(response => response.data));
  }

  getHistoryEntry(id: number): Observable<QueryHistoryEntry> {
    return this.http
      .get<ApiResponse<QueryHistoryEntry>>(`${this.historyBaseUrl}/${id}`)
      .pipe(map(response => response.data));
  }

  deleteHistory(id: number): Observable<void> {
    return this.http.delete<ApiResponse<void>>(`${this.historyBaseUrl}/${id}`).pipe(map(() => undefined));
  }
}

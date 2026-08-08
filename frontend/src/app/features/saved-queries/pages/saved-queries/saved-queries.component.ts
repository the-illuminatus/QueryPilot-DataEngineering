import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialog } from '@angular/material/dialog';
import { finalize } from 'rxjs';

import { SavedQueryService } from '../../../../core/services/saved-query.service';
import { NotificationService } from '../../../../core/services/notification.service';
import { extractErrorMessage } from '../../../../shared/utils/http-error.util';
import { SavedQueryResponse } from '../../../../shared/models/saved-query.model';
import { ConfirmDialogComponent, ConfirmDialogData } from '../../../../shared/components/confirm-dialog/confirm-dialog.component';
import { SavedQueryDetailDialogComponent } from '../../components/saved-query-detail-dialog/saved-query-detail-dialog.component';
import {
  RenameSavedQueryDialogComponent,
  RenameSavedQueryDialogData
} from '../../components/rename-saved-query-dialog/rename-saved-query-dialog.component';

@Component({
  selector: 'qp-saved-queries',
  imports: [
    DatePipe,
    MatCardModule,
    MatTableModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule
  ],
  templateUrl: './saved-queries.component.html',
  styleUrl: './saved-queries.component.scss'
})
export class SavedQueriesComponent {
  private readonly savedQueryService = inject(SavedQueryService);
  private readonly notificationService = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly displayedColumns = ['title', 'question', 'createdAt', 'updatedAt', 'actions'];

  readonly savedQueries = signal<SavedQueryResponse[]>([]);
  readonly isLoading = signal(true);
  readonly deletingId = signal<number | null>(null);
  readonly isDeleting = computed(() => this.deletingId() !== null);

  constructor() {
    this.loadSavedQueries();
  }

  view(savedQuery: SavedQueryResponse): void {
    this.dialog.open(SavedQueryDetailDialogComponent, { width: '560px', data: savedQuery });
  }

  rename(savedQuery: SavedQueryResponse): void {
    this.dialog
      .open<RenameSavedQueryDialogComponent, RenameSavedQueryDialogData, string>(RenameSavedQueryDialogComponent, {
        width: '420px',
        data: { currentTitle: savedQuery.title }
      })
      .afterClosed()
      .subscribe(title => {
        if (title && title !== savedQuery.title) {
          this.renameSavedQuery(savedQuery.id, title);
        }
      });
  }

  confirmDelete(savedQuery: SavedQueryResponse): void {
    this.dialog
      .open<ConfirmDialogComponent, ConfirmDialogData, boolean>(ConfirmDialogComponent, {
        width: '400px',
        data: {
          title: 'Delete saved query?',
          message: `This will permanently delete "${savedQuery.title}". This action cannot be undone.`,
          confirmLabel: 'Delete'
        }
      })
      .afterClosed()
      .subscribe(confirmed => {
        if (confirmed) {
          this.deleteSavedQuery(savedQuery.id);
        }
      });
  }

  private loadSavedQueries(showSpinner = true): void {
    if (showSpinner) {
      this.isLoading.set(true);
    }

    this.savedQueryService
      .getSavedQueries()
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: savedQueries => this.savedQueries.set(savedQueries),
        error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
      });
  }

  private renameSavedQuery(id: number, title: string): void {
    this.savedQueryService.renameSavedQuery(id, title).subscribe({
      next: () => {
        this.loadSavedQueries(false);
        this.notificationService.success('Saved query renamed.');
      },
      error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
    });
  }

  private deleteSavedQuery(id: number): void {
    this.deletingId.set(id);
    this.savedQueryService
      .deleteSavedQuery(id)
      .pipe(finalize(() => this.deletingId.set(null)))
      .subscribe({
        next: () => {
          this.loadSavedQueries(false);
          this.notificationService.success('Saved query deleted.');
        },
        error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
      });
  }
}

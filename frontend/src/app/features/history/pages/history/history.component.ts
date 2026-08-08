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

import { HistoryService } from '../../../../core/services/history.service';
import { NotificationService } from '../../../../core/services/notification.service';
import { extractErrorMessage } from '../../../../shared/utils/http-error.util';
import { QueryHistoryEntry } from '../../../../shared/models/history.model';
import { ConfirmDialogComponent, ConfirmDialogData } from '../../../../shared/components/confirm-dialog/confirm-dialog.component';
import { HistoryDetailDialogComponent } from '../../components/history-detail-dialog/history-detail-dialog.component';

@Component({
  selector: 'qp-history',
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
  templateUrl: './history.component.html',
  styleUrl: './history.component.scss'
})
export class HistoryComponent {
  private readonly historyService = inject(HistoryService);
  private readonly notificationService = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly displayedColumns = ['executedAt', 'question', 'executionTimeMs', 'rowCount', 'status', 'actions'];

  readonly entries = signal<QueryHistoryEntry[]>([]);
  readonly isLoading = signal(true);
  readonly deletingId = signal<number | null>(null);
  readonly isDeleting = computed(() => this.deletingId() !== null);

  constructor() {
    this.loadHistory();
  }

  viewEntry(entry: QueryHistoryEntry): void {
    this.dialog.open(HistoryDetailDialogComponent, { width: '560px', data: entry });
  }

  confirmDelete(entry: QueryHistoryEntry): void {
    this.dialog
      .open<ConfirmDialogComponent, ConfirmDialogData, boolean>(ConfirmDialogComponent, {
        width: '400px',
        data: {
          title: 'Delete history entry?',
          message: 'This will permanently delete this query history record. This action cannot be undone.',
          confirmLabel: 'Delete'
        }
      })
      .afterClosed()
      .subscribe(confirmed => {
        if (confirmed) {
          this.deleteEntry(entry.id);
        }
      });
  }

  private loadHistory(showSpinner = true): void {
    if (showSpinner) {
      this.isLoading.set(true);
    }

    this.historyService
      .getHistory()
      .pipe(finalize(() => this.isLoading.set(false)))
      .subscribe({
        next: entries => this.entries.set(entries),
        error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
      });
  }

  private deleteEntry(id: number): void {
    this.deletingId.set(id);
    this.historyService
      .deleteHistory(id)
      .pipe(finalize(() => this.deletingId.set(null)))
      .subscribe({
        next: () => {
          this.loadHistory(false);
          this.notificationService.success('Query history entry deleted.');
        },
        error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
      });
  }
}

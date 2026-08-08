import { Component, WritableSignal, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTableModule } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import { Observable, finalize } from 'rxjs';

import { QueryService } from '../../../../core/services/query.service';
import { NotificationService } from '../../../../core/services/notification.service';
import { extractErrorMessage } from '../../../../shared/utils/http-error.util';
import { downloadBlob } from '../../../../shared/utils/download.util';
import { formatCellValue } from '../../../../shared/utils/format-cell.util';
import { QueryExecutionResult } from '../../../../shared/models/query.model';
import { SaveQueryDialogComponent } from '../../components/save-query-dialog/save-query-dialog.component';

const CSV_EXPORT_FILENAME = 'query-results.csv';
const XLSX_EXPORT_FILENAME = 'query-results.xlsx';

@Component({
  selector: 'qp-query',
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTableModule
  ],
  templateUrl: './query.component.html',
  styleUrl: './query.component.scss'
})
export class QueryComponent {
  private readonly fb = inject(FormBuilder);
  private readonly queryService = inject(QueryService);
  private readonly notificationService = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly form = this.fb.nonNullable.group({
    question: ['', [Validators.required, Validators.minLength(10)]]
  });

  readonly isGenerating = signal(false);
  readonly isSaving = signal(false);
  readonly isExportingCsv = signal(false);
  readonly isExportingExcel = signal(false);

  readonly result = signal<QueryExecutionResult | null>(null);
  readonly displayedColumns = computed(() => this.result()?.columns ?? []);

  readonly formatCellValue = formatCellValue;

  /**
   * The question that produced the currently displayed result. Export/Save
   * re-run against this exact text (captured at generate time) rather than
   * the live form value, since editing the question afterwards must not
   * silently change what a subsequent export/save operates on.
   */
  private lastSubmittedQuestion: string | null = null;

  generate(): void {
    if (this.form.invalid || this.isGenerating()) {
      this.form.markAllAsTouched();
      return;
    }

    const question = this.form.getRawValue().question;
    this.isGenerating.set(true);
    this.form.disable();

    this.queryService
      .generateQuery(question)
      .pipe(
        finalize(() => {
          this.isGenerating.set(false);
          this.form.enable();
        })
      )
      .subscribe({
        next: result => {
          this.result.set(result);
          this.lastSubmittedQuestion = question;
        },
        error: (error: HttpErrorResponse) => {
          this.result.set(null);
          this.notificationService.error(extractErrorMessage(error));
        }
      });
  }

  exportCsv(): void {
    this.runExport(this.isExportingCsv, q => this.queryService.exportCsv(q), CSV_EXPORT_FILENAME);
  }

  exportExcel(): void {
    this.runExport(this.isExportingExcel, q => this.queryService.exportExcel(q), XLSX_EXPORT_FILENAME);
  }

  openSaveDialog(): void {
    const result = this.result();
    const question = this.lastSubmittedQuestion;
    if (!result || !question || this.isSaving()) {
      return;
    }

    this.dialog
      .open(SaveQueryDialogComponent, { width: '420px' })
      .afterClosed()
      .subscribe((title: string | undefined) => {
        if (!title) {
          return;
        }

        this.isSaving.set(true);
        this.queryService
          .saveQuery({ title, question, generatedSql: result.sql })
          .pipe(finalize(() => this.isSaving.set(false)))
          .subscribe({
            next: () => this.notificationService.success('Query saved successfully.'),
            error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
          });
      });
  }

  private runExport(loading: WritableSignal<boolean>, exportFn: (question: string) => Observable<Blob>, filename: string): void {
    const question = this.lastSubmittedQuestion;
    if (!question || loading()) {
      return;
    }

    loading.set(true);
    exportFn(question)
      .pipe(finalize(() => loading.set(false)))
      .subscribe({
        next: blob => downloadBlob(blob, filename),
        error: (error: HttpErrorResponse) => this.notificationService.error(extractErrorMessage(error))
      });
  }
}

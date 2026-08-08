import { Component, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { QueryHistoryEntry } from '../../../../shared/models/history.model';

@Component({
  selector: 'qp-history-detail-dialog',
  imports: [DatePipe, MatDialogModule, MatButtonModule, MatIconModule],
  templateUrl: './history-detail-dialog.component.html',
  styleUrl: './history-detail-dialog.component.scss'
})
export class HistoryDetailDialogComponent {
  readonly entry = inject<QueryHistoryEntry>(MAT_DIALOG_DATA);
}

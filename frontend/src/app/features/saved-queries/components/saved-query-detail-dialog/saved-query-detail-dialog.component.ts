import { Component, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

import { SavedQueryResponse } from '../../../../shared/models/saved-query.model';

@Component({
  selector: 'qp-saved-query-detail-dialog',
  imports: [DatePipe, MatDialogModule, MatButtonModule],
  templateUrl: './saved-query-detail-dialog.component.html',
  styleUrl: './saved-query-detail-dialog.component.scss'
})
export class SavedQueryDetailDialogComponent {
  readonly savedQuery = inject<SavedQueryResponse>(MAT_DIALOG_DATA);
}

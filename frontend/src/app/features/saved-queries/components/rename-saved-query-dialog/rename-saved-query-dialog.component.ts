import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';

export interface RenameSavedQueryDialogData {
  currentTitle: string;
}

@Component({
  selector: 'qp-rename-saved-query-dialog',
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  templateUrl: './rename-saved-query-dialog.component.html',
  styleUrl: './rename-saved-query-dialog.component.scss'
})
export class RenameSavedQueryDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly dialogRef = inject(MatDialogRef<RenameSavedQueryDialogComponent, string>);
  private readonly data = inject<RenameSavedQueryDialogData>(MAT_DIALOG_DATA);

  readonly form = this.fb.nonNullable.group({
    title: [this.data.currentTitle, [Validators.required, Validators.maxLength(100)]]
  });

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.dialogRef.close(this.form.getRawValue().title.trim());
  }

  cancel(): void {
    this.dialogRef.close();
  }
}

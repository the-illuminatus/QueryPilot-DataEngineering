import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly snackBar = inject(MatSnackBar);

  error(message: string): void {
    this.snackBar.open(message, 'Dismiss', { duration: 5000, panelClass: 'qp-snackbar--error' });
  }

  success(message: string): void {
    this.snackBar.open(message, 'Dismiss', { duration: 3000, panelClass: 'qp-snackbar--success' });
  }
}

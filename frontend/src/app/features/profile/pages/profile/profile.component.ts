import { Component, inject } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';

import { AuthService } from '../../../../core/services/auth.service';

interface TechStackItem {
  icon: string;
  label: string;
}

@Component({
  selector: 'qp-profile',
  imports: [MatCardModule, MatIconModule, MatButtonModule, MatDividerModule],
  templateUrl: './profile.component.html',
  styleUrl: './profile.component.scss'
})
export class ProfileComponent {
  private readonly authService = inject(AuthService);

  readonly currentUser = this.authService.currentUser;

  readonly appName = 'QueryPilot';
  readonly appVersion = '1.0.0';

  readonly techStack: TechStackItem[] = [
    { icon: 'language', label: 'Angular' },
    { icon: 'dns', label: 'Spring Boot' },
    { icon: 'storage', label: 'PostgreSQL' },
    { icon: 'auto_awesome', label: 'Google Gemini' }
  ];

  logout(): void {
    this.authService.logout();
  }
}

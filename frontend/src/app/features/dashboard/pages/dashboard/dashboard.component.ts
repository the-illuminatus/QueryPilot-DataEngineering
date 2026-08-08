import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';

import { AuthService } from '../../../../core/services/auth.service';

interface QuickAction {
  label: string;
  icon: string;
  route: string;
}

interface FeatureHighlight {
  icon: string;
  title: string;
  description: string;
  route?: string;
}

@Component({
  selector: 'qp-dashboard',
  imports: [RouterLink, MatCardModule, MatIconModule, MatButtonModule, MatDividerModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent {
  private readonly authService = inject(AuthService);

  readonly currentUser = this.authService.currentUser;

  readonly quickActions: QuickAction[] = [
    { label: 'Ask AI', icon: 'auto_awesome', route: '/query' },
    { label: 'Query History', icon: 'history', route: '/history' },
    { label: 'Saved Queries', icon: 'bookmark', route: '/saved-queries' },
    { label: 'Profile', icon: 'person', route: '/profile' }
  ];

  readonly features: FeatureHighlight[] = [
    {
      icon: 'auto_awesome',
      title: 'AI SQL Generation',
      description: 'Describe what you need in plain English and let QueryPilot generate accurate SQL for you.',
      route: '/query'
    },
    {
      icon: 'play_circle',
      title: 'SQL Execution',
      description: 'Run generated queries directly against your connected database and view the results instantly.',
      route: '/query'
    },
    {
      icon: 'history',
      title: 'Query History',
      description: 'Revisit every query you have run, complete with timestamps and outcomes.',
      route: '/history'
    },
    {
      icon: 'bookmark',
      title: 'Saved Queries',
      description: 'Bookmark frequently used queries so they are one click away whenever you need them.',
      route: '/saved-queries'
    },
    {
      icon: 'description',
      title: 'CSV Export',
      description: 'Export any result set to CSV for spreadsheets, reporting, or downstream analysis.'
    },
    {
      icon: 'table_chart',
      title: 'Excel Export',
      description: 'Export results directly to a formatted Excel workbook, ready to share.'
    }
  ];
}

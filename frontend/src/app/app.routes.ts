import { Routes } from '@angular/router';

import { MainLayoutComponent } from './core/layout/main-layout/main-layout.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/pages/login/login.component').then(m => m.LoginComponent)
  },
  {
    path: 'register',
    loadComponent: () =>
      import('./features/auth/pages/register/register.component').then(m => m.RegisterComponent)
  },
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/pages/dashboard/dashboard.component').then(m => m.DashboardComponent)
      },
      {
        path: 'query',
        loadComponent: () =>
          import('./features/query/pages/query/query.component').then(m => m.QueryComponent)
      },
      {
        path: 'history',
        loadComponent: () =>
          import('./features/history/pages/history/history.component').then(m => m.HistoryComponent)
      },
      {
        path: 'saved-queries',
        loadComponent: () =>
          import('./features/saved-queries/pages/saved-queries/saved-queries.component').then(
            m => m.SavedQueriesComponent
          )
      },
      {
        path: 'profile',
        loadComponent: () =>
          import('./features/profile/pages/profile/profile.component').then(m => m.ProfileComponent)
      }
    ]
  },
  { path: '**', redirectTo: 'dashboard' }
];

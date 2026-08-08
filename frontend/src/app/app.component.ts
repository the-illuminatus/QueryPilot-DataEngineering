import { Component } from '@angular/core';

import { MainLayoutComponent } from './core/layout/main-layout/main-layout.component';

@Component({
  selector: 'qp-root',
  imports: [MainLayoutComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {}

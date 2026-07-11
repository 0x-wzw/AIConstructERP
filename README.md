# ConstructERP 🏗️

**Construction Project Management Suite** — a dark glassmorphism ERP dashboard for construction project management.

![Version](https://img.shields.io/badge/version-2.0.0-amber)
![Status](https://img.shields.io/badge/status-prototype-yellow)

## Features

- **Dashboard** — KPI cards, Budget vs Actual chart (Chart.js), alerts, activity feed, milestones
- **Projects** — Create, view, and manage construction projects with budget tracking
- **Schedule** — Gantt chart for task scheduling and timeline visualization
- **Resources** — Track labor, equipment, and materials inventory
- **Budget** — Cost breakdown table with search, budget vs committed vs spent tracking
- **Procurement** — Purchase order management with search and status filtering
- **Subcontractors** — Subcontractor directory with contract and progress tracking
- **Reports** — Exportable data and report generation

## Tech Stack

| Layer | Technology |
|---|---|
| **UI** | Vanilla JS + Tailwind CSS (CDN) |
| **Icons** | Lucide (CDN) |
| **Charts** | Chart.js 4.4.7 (CDN) |
| **Persistence** | localStorage |
| **Fonts** | Inter + JetBrains Mono (Google Fonts) |

## Getting Started

Just open `construct_erp.html` in any modern browser — no build step, no server required.

```bash
open construct_erp.html
```

## Roadmap to Enterprise

- [ ] Backend API (FastAPI + PostgreSQL)
- [ ] Auth (OAuth2/OIDC, RBAC, MFA)
- [ ] Frontend framework (React/Vite)
- [ ] Real CRUD with API persistence
- [ ] Multi-tenancy & audit logging
- [ ] CI/CD, automated tests, WCAG compliance

## License

MIT

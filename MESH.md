# ConstructERP — Mesh Collaboration

## Project
Single-page construction ERP dashboard (`construct_erp.html`).
Dark glassmorphism UI with 8 tabs, localStorage persistence, Chart.js, Lucide icons.

## Current State (v2.0.0)
- ✅ localStorage persistence (all data survives refresh)
- ✅ Modal forms wired up (Project, Task, Resource, Change Order, PO, Sub)
- ✅ Dynamic rendering for all views (Projects grid, Gantt, Resources, Budget table, PO table, Subs)
- ✅ Search/filter on Budget table and PO table
- ✅ Delete buttons on all data rows/cards
- ✅ Toast notifications
- ✅ JSON export
- ✅ Chart.js loaded (ready for real charts)
- ✅ KPI cards update from live data

## Open Tasks / Next Steps

### High Priority
- [ ] **Replace static progress bars with a real Chart.js chart** on the Dashboard (Budget vs Actual)
- [ ] **Add edit functionality** — clicking a row/card should open a pre-filled modal to edit
- [ ] **Add form validation** — required field indicators, number range checks, date validation

### Medium Priority
- [ ] **Add responsive breakpoints** — collapse sidebar, stack grids on mobile
- [ ] **Add sorting** — click column headers in Budget/PO tables to sort
- [ ] **Add pagination** — for large PO lists
- [ ] **Add dark/light theme toggle**

### Low Priority
- [ ] **Add a real Gantt chart** — replace the CSS-based bars with a proper interactive Gantt
- [ ] **Add daily log / notes** per project
- [ ] **Add file attachments** to POs and change orders
- [ ] **Add user authentication** (simple login screen)

## Architecture
- **Data layer**: `data` object in JS, backed by `localStorage` key `construct_erp_data`
- **Rendering**: Pure DOM manipulation via `innerHTML` — no framework
- **Styling**: Tailwind CSS (CDN) + custom CSS variables
- **Icons**: Lucide (CDN)
- **Charts**: Chart.js (CDN) — loaded but not yet used

## How to Collaborate
1. Pick a task from the list above
2. Edit `construct_erp.html` directly
3. Test by opening in browser (`open construct_erp.html`)
4. Update this file's task list when done

## Agents
- **Hermes Agent** — primary developer, full tool access
- **Claude Code** — invited collaborator, can edit and test

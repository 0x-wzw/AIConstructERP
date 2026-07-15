# ConstructERP — Frontend ↔ API Integration

This folder wires a browser UI to the FastAPI backend: JWT login, an
authenticated API client, and a live, role-aware dashboard. It's **additive** —
it does not modify the standalone `construct_erp.html` (which is a separate,
`localStorage`-only line of development).

## Files

| File | Purpose |
|------|---------|
| `api.js` | Dependency-free API client: login, token storage, `authFetch`, CRUD per resource, role helpers |
| `login.html` | Sign-in screen (OAuth2 password flow) with demo-account shortcuts |
| `app.html` | Live dashboard — auth-gated, renders `/api/state`, role-aware create/delete |

## Run it

```bash
# 1. Start the backend
cd ../backend && uv run uvicorn app.main:app --port 8787

# 2. Serve this folder over http:// (not file://, so fetch/CORS behave)
cd ../frontend && python3 -m http.server 5173
#   → open http://localhost:5173/login.html
```

Sign in with a demo account (or the buttons on the login screen):

| Button / Email                     | Password    | Backend role      |
|------------------------------------|-------------|-------------------|
| Superadmin · superadmin@…dev       | super123    | admin             |
| Vendor · vendor@…dev               | vendor123   | project_manager   |
| Supplier · supplier@…dev           | supplier123 | accounting        |

Log in as **Vendor** → you can add projects but the **New PO** button is hidden.
Log in as **Supplier** → the reverse. The server enforces this too (403), so the
UI hiding is convenience, not the security boundary.

## Role reconciliation

The frontend's business vocabulary maps onto the backend's security roles:

| Frontend role | Backend role      | Can write                                   |
|---------------|-------------------|---------------------------------------------|
| **Superadmin**| `admin`           | everything                                  |
| **Vendor**    | `project_manager` | projects, tasks, resources, subcontractors  |
| **Supplier**  | `accounting`      | budget, purchase orders                     |
| _(Viewer)_    | `viewer`          | nothing (read-only)                         |

This mapping lives in one place — `api.js` → `ROLE_MAP` / `ROLE_LABEL` /
`WRITE_ROLES` — kept in sync with the server's per-resource `write_roles`.

## Using the client from any page

```html
<script src="api.js"></script>
<script>
  await ConstructERP.login('vendor@constructerp.dev', 'vendor123');
  const state = await ConstructERP.state();          // full app state, one call
  const p = await ConstructERP.projects.create({ name: 'New Tower', budget: 750000 });
  await ConstructERP.projects.update(p.id, { progress: 25 });
  await ConstructERP.projects.remove(p.id);
  if (ConstructERP.canWrite('budget')) { /* show budget editor */ }
</script>
```

`authFetch` handles auth automatically: attaches the bearer token, clears it and
surfaces a friendly message on `401`, and reports `403` without logging you out.

## Migrating `construct_erp.html` onto the API (drop-in)

The standalone app keeps data in a `data` object persisted to `localStorage`.
To move it onto the backend, replace three things:

1. **Gate on auth** — at startup, `if (!ConstructERP.isAuthed()) location.href = 'login.html'`.
2. **Load** — replace `loadData()` with `await ConstructERP.state()` and map the
   returned shape (`projects`, `tasks`, `resources`, `budget`, `pos`, `subs`,
   `changeOrders`) into the render functions.
3. **Persist** — replace each `data.push(...) + saveData()` and `deleteX()` with
   the matching `ConstructERP.<resource>.create/update/remove(...)` call, then
   re-fetch.

Because it's the same field names, the render layer barely changes — only the
data source and the write paths do.

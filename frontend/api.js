/**
 * ConstructERP API client.
 *
 * A dependency-free wrapper around the FastAPI backend: JWT login, token
 * storage, authenticated fetch with 401/403 handling, and CRUD helpers for
 * every resource. Drop this into any page with:  <script src="api.js"></script>
 * and call `ConstructERP.login(...)` / `ConstructERP.projects.list()` etc.
 */
const ConstructERP = (() => {
  const TOKEN_KEY = 'construct_erp_token';
  const ROLE_KEY = 'construct_erp_backend_role';
  const BASE_KEY = 'construct_erp_api_base';

  let BASE = localStorage.getItem(BASE_KEY) || 'http://localhost:8787';

  // ── Role reconciliation ─────────────────────────────────────────────
  // Frontend business role  ->  backend security role
  const ROLE_MAP = {
    superadmin: 'admin',
    vendor: 'project_manager',
    supplier: 'accounting',
  };
  // Backend security role  ->  frontend display label
  const ROLE_LABEL = {
    admin: 'Superadmin',
    project_manager: 'Vendor',
    accounting: 'Supplier',
    viewer: 'Viewer',
  };
  // Which backend roles may write each section (mirrors the server; used only
  // to enable/disable UI — the server remains the real enforcement point).
  const WRITE_ROLES = {
    projects: ['admin', 'project_manager'],
    tasks: ['admin', 'project_manager'],
    resources: ['admin', 'project_manager'],
    subs: ['admin', 'project_manager'],
    budget: ['admin', 'accounting'],
    pos: ['admin', 'accounting'],
    changeOrders: ['admin', 'accounting', 'project_manager'],
  };

  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  }

  function setBaseUrl(url) { BASE = url.replace(/\/$/, ''); localStorage.setItem(BASE_KEY, BASE); }
  function baseUrl() { return BASE; }
  function token() { return localStorage.getItem(TOKEN_KEY); }
  function role() { return localStorage.getItem(ROLE_KEY); }
  function isAuthed() { return !!token(); }
  function roleLabel() { return ROLE_LABEL[role()] || role() || 'Guest'; }
  function canWrite(section) { return (WRITE_ROLES[section] || []).includes(role()); }

  function qs(params) {
    const clean = {};
    for (const [k, v] of Object.entries(params || {})) {
      if (v !== undefined && v !== null && v !== '') clean[k] = v;
    }
    const s = new URLSearchParams(clean).toString();
    return s ? `?${s}` : '';
  }

  async function login(email, password) {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail || 'Login failed';
      throw new ApiError(detail, res.status);
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(ROLE_KEY, data.role);
    return data;
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
  }

  async function authFetch(path, opts = {}) {
    const headers = Object.assign({}, opts.headers);
    if (token()) headers['Authorization'] = `Bearer ${token()}`;
    if (opts.body && typeof opts.body === 'string') headers['Content-Type'] = 'application/json';
    let res;
    try {
      res = await fetch(`${BASE}${path}`, { ...opts, headers });
    } catch (e) {
      throw new ApiError(`Cannot reach API at ${BASE} — is the backend running?`, 0);
    }
    if (res.status === 401) { logout(); throw new ApiError('Session expired — please log in again.', 401); }
    if (res.status === 403) { throw new ApiError('You do not have permission for this action.', 403); }
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(detailOf(data) || `Request failed (${res.status})`, res.status);
    return data;
  }

  // FastAPI validation errors arrive as {detail: [{loc, msg}, ...]}.
  function detailOf(data) {
    if (!data || !data.detail) return null;
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(e => `${(e.loc || []).slice(-1)[0] || ''}: ${e.msg}`).join('; ');
    }
    return null;
  }

  const api = {
    ApiError, ROLE_MAP, ROLE_LABEL, WRITE_ROLES,
    setBaseUrl, baseUrl, login, logout, isAuthed, token, role, roleLabel, canWrite,
    me: () => authFetch('/api/auth/me'),
    state: () => authFetch('/api/state'),
    health: () => authFetch('/api/health'),
    users: {
      list: () => authFetch('/api/auth/users'),
      create: (data) => authFetch('/api/auth/users', { method: 'POST', body: JSON.stringify(data) }),
      update: (id, data) => authFetch(`/api/auth/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    },
  };

  // CRUD helpers: api.projects.list() / .create() / .update() / .remove()
  const RESOURCES = {
    projects: 'projects',
    tasks: 'tasks',
    resources: 'resources',
    budget: 'budget',
    pos: 'purchase-orders',
    subs: 'subcontractors',
    changeOrders: 'change-orders',
  };
  for (const [key, path] of Object.entries(RESOURCES)) {
    api[key] = {
      list: (params) => authFetch(`/api/${path}${qs(params)}`),
      get: (id) => authFetch(`/api/${path}/${id}`),
      create: (data) => authFetch(`/api/${path}`, { method: 'POST', body: JSON.stringify(data) }),
      update: (id, data) => authFetch(`/api/${path}/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
      remove: (id) => authFetch(`/api/${path}/${id}`, { method: 'DELETE' }),
    };
  }

  return api;
})();

if (typeof module !== 'undefined' && module.exports) module.exports = ConstructERP;

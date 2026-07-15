/**
 * API client — handles auth, token refresh, and typed requests.
 */

const BASE = "/api";

let accessToken: string | null = localStorage.getItem("access_token");
let refreshToken: string | null = localStorage.getItem("refresh_token");

export function setTokens(access: string, refresh?: string) {
  accessToken = access;
  localStorage.setItem("access_token", access);
  if (refresh) {
    refreshToken = refresh;
    localStorage.setItem("refresh_token", refresh);
  }
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function isAuthed(): boolean {
  return !!accessToken;
}

export function getRole(): string | null {
  return localStorage.getItem("role");
}

async function refresh(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false  ;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  let res = await fetch(`${BASE}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401 && refreshToken) {
    const refreshed = await refresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      res = await fetch(`${BASE}${path}`, { ...options, headers });
    } else {
      clearTokens();
      window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ─────────────────────────────────────────────────────────────
export const api = {
  async login(email: string, password: string) {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    const res = await fetch(`${BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    localStorage.setItem("role", data.role);
    return data;
  },

  async me() {
    return request<{ id: number; email: string; role: string; full_name: string }>(
      "/auth/me"
    );
  },

  async health() {
    return request<{ status: string; version: string; ai_available: boolean }>(
      "/health"
    );
  },

  // ── Generic CRUD ─────────────────────────────────────────────────────
  async list<T>(resource: string, params?: Record<string, string>): Promise<T[]> {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<T[]>(`/${resource}${qs}`);
  },

  async get<T>(resource: string, id: number): Promise<T> {
    return request<T>(`/${resource}/${id}`);
  },

  async create<T>(resource: string, data: unknown): Promise<T> {
    return request<T>(`/${resource}`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async update<T>(resource: string, id: number, data: unknown): Promise<T> {
    return request<T>(`/${resource}/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async delete(resource: string, id: number): Promise<void> {
    return request<void>(`/${resource}/${id}`, { method: "DELETE" });
  },

  // ── Files ────────────────────────────────────────────────────────────
  async uploadFile(file: File, category?: string): Promise<unknown> {
    const form = new FormData();
    form.append("file", file);
    if (category) form.append("category", category);
    const res = await fetch(`${BASE}/files/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: form,
    });
    if (!res.ok) throw new Error("Upload failed");
    return res.json();
  },

  async ocrFile(fileId: number): Promise<unknown> {
    return request<{ text: string; word_count: number }>(
      `/files/${fileId}/ocr`,
      { method: "POST" }
    );
  },

  // ── AI Chat ──────────────────────────────────────────────────────────
  async createChatSession(title: string) {
    return request<{ id: number; title: string }>("/ai/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  },

  async listChatSessions() {
    return request<{ id: number; title: string; created_at: string }[]>(
      "/ai/chat/sessions"
    );
  },

  async listChatMessages(sessionId: number) {
    return request<{ id: number; role: string; content: string }[]>(
      `/ai/chat/sessions/${sessionId}/messages`
    );
  },

  async sendChatMessage(sessionId: number, content: string) {
    return request<{ id: number; role: string; content: string }>(
      `/ai/chat/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, role: "user", content }),
      }
    );
  },

  // ── Reverse Auction ─────────────────────────────────────────────────
  async placeAuctionBid(auctionId: number, vendorId: number, amount: number) {
    return request<{ id: number; bid_amount: number; is_leading: boolean }>(
      `/reverse-auctions/${auctionId}/bids`,
      {
        method: "POST",
        body: JSON.stringify({ auction_id: auctionId, vendor_id: vendorId, bid_amount: amount }),
      }
    );
  },

  async auctionLeaderboard(auctionId: number) {
    return request<{ id: number; bid_amount: number; is_leading: boolean }[]>(
      `/reverse-auctions/${auctionId}/leaderboard`
    );
  },

  // ── Audit Log ────────────────────────────────────────────────────────
  async auditLog(entityType?: string) {
    const qs = entityType ? `?entity_type=${entityType}` : "";
    return request<{ id: number; action: string; entity_type: string; summary: string; user_email: string; created_at: string }[]>(
      `/audit${qs}`
    );
  },

  // ── State ────────────────────────────────────────────────────────────
  async fullState() {
    return request<Record<string, unknown>>("/state");
  },
};
import React, { useState, useEffect } from "react";
import { api, isAuthed, clearTokens, getRole } from "./api";

type Tab =
  | "dashboard" | "projects" | "tenders" | "vendors" | "contracts"
  | "consultants" | "cde" | "procurement" | "cost" | "reports"
  | "files" | "ai" | "audit" | "admin";

const TABS: { key: Tab; label: string; roles?: string[] }[] = [
  { key: "dashboard", label: "Dashboard" },
  { key: "projects", label: "Projects" },
  { key: "tenders", label: "Tenders & Bidding" },
  { key: "vendors", label: "Vendors" },
  { key: "contracts", label: "Contracts" },
  { key: "consultants", label: "Consultants" },
  { key: "cde", label: "CDE" },
  { key: "procurement", label: "Procurement" },
  { key: "cost", label: "Cost Data" },
  { key: "reports", label: "Reports" },
  { key: "files", label: "Files" },
  { key: "ai", label: "AI Assistant", roles: ["project_manager", "admin"] },
  { key: "audit", label: "Audit Log" },
  { key: "admin", label: "Admin", roles: ["admin"] },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [authed, setAuthed] = useState(isAuthed());
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [role, setRole] = useState(getRole());
  const [health, setHealth] = useState<{ status: string; version: string; ai_available: boolean } | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const data = await api.login(email, password);
      setRole(data.role);
      setAuthed(true);
    } catch (err) {
      setError("Invalid credentials");
    }
  }

  function handleLogout() {
    clearTokens();
    setAuthed(false);
    setRole(null);
  }

  if (!authed) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <form onSubmit={handleLogin} className="glass" style={{ padding: 32, width: 360, display: "flex", flexDirection: "column", gap: 16 }}>
          <h1 style={{ color: "var(--white)", fontSize: 20, fontWeight: 700 }}>
            Construct<span style={{ color: "var(--amber)" }}>ERP</span>
          </h1>
          {health && (
            <div style={{ fontSize: 12, color: "var(--green)" }}>
              ● API v{health.version} {health.ai_available ? "• AI Online" : ""}
            </div>
          )}
          {error && <div style={{ color: "var(--rose)", fontSize: 13 }}>{error}</div>}
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button type="submit" className="btn btn-primary">Sign In</button>
          <div style={{ fontSize: 11, color: "var(--slate)" }}>
            Demo: admin@constructerp.dev / admin123
          </div>
        </form>
      </div>
    );
  }

  const visibleTabs = TABS.filter(t => !t.roles || (role && t.roles.includes(role)));

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Header */}
      <header className="glass" style={{ height: 56, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", borderBottom: "1px solid var(--border)", position: "sticky", top: 0, zIndex: 10, borderRadius: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, var(--amber), #d97706)", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontWeight: 700, fontSize: 14 }}>CE</div>
          <div>
            <div style={{ color: "var(--white)", fontWeight: 700, fontSize: 14 }}>Construct<span style={{ color: "var(--amber)" }}>ERP</span></div>
            {health && <div style={{ fontSize: 10, color: "var(--green)" }}>v{health.version} {health.ai_available ? "• AI Online" : ""}</div>}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span style={{ fontSize: 12, color: "var(--white)" }}>{role}</span>
          <button onClick={handleLogout} className="btn btn-ghost" style={{ fontSize: 12 }}>Sign Out</button>
        </div>
      </header>

      {/* Body */}
      <div style={{ display: "flex", minHeight: "calc(100vh - 56px)" }}>
        {/* Sidebar */}
        <nav style={{ width: 220, padding: 16, display: "flex", flexDirection: "column", gap: 4 }}>
          {visibleTabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="btn btn-ghost"
              style={{
                textAlign: "left",
                padding: "10px 14px",
                borderRadius: 8,
                fontWeight: tab === t.key ? 600 : 400,
                background: tab === t.key ? "rgba(245,158,11,0.1)" : "transparent",
                color: tab === t.key ? "var(--amber)" : "var(--text)",
                border: "none",
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {/* Content */}
        <main style={{ flex: 1, padding: 24, overflowY: "auto" }}>
          {tab === "dashboard" && <Dashboard />}
          {tab === "projects" && <CrudView resource="projects" title="Projects" fields={["name", "location", "budget", "progress", "status"]} />}
          {tab === "tenders" && <TenderView />}
          {tab === "vendors" && <CrudView resource="vendors" title="Vendors" fields={["name", "category", "status", "rating"]} />}
          {tab === "contracts" && <ContractView />}
          {tab === "consultants" && <CrudView resource="consultants" title="Consultants" fields={["name", "firm", "discipline", "status"]} />}
          {tab === "cde" && <CDEView />}
          {tab === "procurement" && <ProcurementView />}
          {tab === "cost" && <CostView />}
          {tab === "reports" && <ReportsView />}
          {tab === "files" && <FilesView />}
          {tab === "ai" && <AIView />}
          {tab === "audit" && <AuditView />}
          {tab === "admin" && <AdminView />}
        </main>
      </div>
    </div>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────
function Dashboard() {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.fullState().then(setState).catch(() => {}); }, []);

  if (!state) return <div>Loading...</div>;
  const projects = (state.projects as any[]) || [];
  const budget = (state.budget as any[]) || [];
  const pos = (state.pos as any[]) || [];

  const totalBudget = budget.reduce((s, b) => s + (b.budget || 0), 0);
  const totalSpent = budget.reduce((s, b) => s + (b.spent || 0), 0);
  const poTotal = pos.reduce((s, p) => s + (p.amount || 0), 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <KPI label="Projects" value={projects.length} color="var(--blue)" />
        <KPI label="Budget" value={`$${Math.round(totalBudget).toLocaleString()}`} color="var(--amber)" />
        <KPI label="Spent" value={`$${Math.round(totalSpent).toLocaleString()}`} color="var(--rose)" />
        <KPI label="Open POs" value={`$${Math.round(poTotal).toLocaleString()}`} color="var(--green)" />
      </div>
      <section className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 16 }}>Projects</h3>
        <table>
          <thead><tr><th>Name</th><th>Location</th><th>Budget</th><th>Progress</th><th>Status</th></tr></thead>
          <tbody>
            {projects.map(p => (
              <tr key={p.id}>
                <td style={{ color: "var(--white)" }}>{p.name}</td>
                <td>{p.location}</td>
                <td>${(p.budget || 0).toLocaleString()}</td>
                <td>{p.progress || 0}%</td>
                <td><span className={`badge badge-${p.status === "active" ? "active" : "pending"}`}>{p.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function KPI({ label, value, color }: { label: string; value: any; color: string }) {
  return (
    <div className="glass" style={{ padding: 20 }}>
      <div style={{ fontSize: 12, color: "var(--slate)", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

// ── Generic CRUD View ────────────────────────────────────────────────
function CrudView({ resource, title, fields }: { resource: string; title: string; fields: string[] }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    try { setItems(await api.list<any>(resource)); } catch {}
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    try {
      const data: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(formData)) {
        if (v) data[k] = isNaN(Number(v)) ? v : Number(v);
      }
      await api.create(resource, data);
      setShowForm(false);
      setFormData({});
      load();
    } catch (err) { alert(`Error: ${err}`); }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this item?")) return;
    try { await api.delete(resource, id); load(); } catch {}
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ color: "var(--white)", fontSize: 18 }}>{title}</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn btn-primary">
          {showForm ? "Cancel" : "+ New"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="glass" style={{ padding: 20, marginBottom: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {fields.map(f => (
            <input key={f} placeholder={f} value={formData[f] || ""} onChange={e => setFormData({ ...formData, [f]: e.target.value })} required={f === "name" || f === "title"} />
          ))}
          <button type="submit" className="btn btn-primary">Create</button>
        </form>
      )}

      {loading ? <div>Loading...</div> : (
        <div className="glass" style={{ overflowX: "auto" }}>
          <table>
            <thead><tr>{fields.map(f => <th key={f}>{f}</th>)}<th></th></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id}>
                  {fields.map(f => <td key={f} style={{ color: f === "name" || f === "title" ? "var(--white)" : "inherit" }}>{typeof item[f] === "number" && f.includes("amount") || f === "budget" || f === "contract" ? `$${(item[f] || 0).toLocaleString()}` : item[f]}</td>)}
                  <td><button onClick={() => handleDelete(item.id)} className="btn btn-ghost" style={{ fontSize: 11, color: "var(--rose)" }}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Tender View (with BOQ and Auction) ────────────────────────────────
function TenderView() {
  const [tenders, setTenders] = useState<any[]>([]);
  const [vendors, setVendors] = useState<any[]>([]);
  const [auctions, setAuctions] = useState<any[]>([]);
  const [selectedTender, setSelectedTender] = useState<number | null>(null);
  const [boqItems, setBoqItems] = useState<any[]>([]);

  useEffect(() => {
    api.list<any>("tenders").then(setTenders).catch(() => {});
    api.list<any>("vendors").then(setVendors).catch(() => {});
    api.list<any>("reverse-auctions").then(setAuctions).catch(() => {});
  }, []);

  async function loadBOQ(tenderId: number) {
    setSelectedTender(tenderId);
    const items = await api.list<any>("boq-items").catch(() => []);
    setBoqItems(items.filter(i => i.tender_id === tenderId));
  }

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Tenders & Bidding</h2>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Tenders</h3>
        <table>
          <thead><tr><th>Title</th><th>Status</th><th>Type</th><th>BOQ</th></tr></thead>
          <tbody>
            {tenders.map(t => (
              <tr key={t.id}>
                <td style={{ color: "var(--white)" }}>{t.title}</td>
                <td><span className={`badge badge-${t.status === "awarded" ? "active" : "pending"}`}>{t.status}</span></td>
                <td>{t.tender_type}</td>
                <td><button onClick={() => loadBOQ(t.id)} className="btn btn-ghost" style={{ fontSize: 11 }}>View BOQ</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedTender && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>BOQ Items</h3>
          <table>
            <thead><tr><th>Item No</th><th>Description</th><th>Unit</th><th>Qty</th><th>Rate</th></tr></thead>
            <tbody>
              {boqItems.map(b => (
                <tr key={b.id}>
                  <td>{b.item_no}</td><td>{b.description}</td><td>{b.unit}</td>
                  <td>{b.quantity}</td><td>${(b.rate || 0).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Reverse Auctions</h3>
        <table>
          <thead><tr><th>ID</th><th>Tender ID</th><th>Status</th><th>Reserve Price</th><th>Leading Amount</th></tr></thead>
          <tbody>
            {auctions.map(a => (
              <tr key={a.id}>
                <td>#{a.id}</td><td>Tender #{a.tender_id}</td>
                <td><span className={`badge badge-${a.status === "active" ? "active" : "pending"}`}>{a.status}</span></td>
                <td>${(a.reserve_price || 0).toLocaleString()}</td>
                <td style={{ color: a.leading_amount > 0 ? "var(--amber)" : "inherit" }}>
                  {a.leading_amount > 0 ? `$${a.leading_amount.toLocaleString()}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Contract View ─────────────────────────────────────────────────────
function ContractView() {
  const [claims, setClaims] = useState<any[]>([]);
  const [certs, setCerts] = useState<any[]>([]);
  const [finalAccounts, setFinalAccounts] = useState<any[]>([]);

  useEffect(() => {
    api.list<any>("progress-claims").then(setClaims).catch(() => {});
    api.list<any>("payment-certificates").then(setCerts).catch(() => {});
    api.list<any>("final-accounts").then(setFinalAccounts).catch(() => {});
  }, []);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Contract Management</h2>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Progress Claims</h3>
        <table><thead><tr><th>Claim No</th><th>Period</th><th>Claim Amount</th><th>Certified</th><th>Status</th></tr></thead>
          <tbody>{claims.map(c => <tr key={c.id}><td>{c.claim_no}</td><td>{c.period}</td><td>${(c.claim_amount||0).toLocaleString()}</td><td>${(c.certified_amount||0).toLocaleString()}</td><td><span className={`badge badge-${c.status === "certified" ? "active" : "pending"}`}>{c.status}</span></td></tr>)}</tbody>
        </table>
      </div>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Payment Certificates</h3>
        <table><thead><tr><th>Cert No</th><th>Gross</th><th>Retention</th><th>Net</th><th>Status</th></tr></thead>
          <tbody>{certs.map(c => <tr key={c.id}><td>{c.certificate_no}</td><td>${(c.gross_amount||0).toLocaleString()}</td><td>${(c.retention_amount||0).toLocaleString()}</td><td>${(c.net_amount||0).toLocaleString()}</td><td>{c.status}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Final Accounts</h3>
        <table><thead><tr><th>Account No</th><th>Original Sum</th><th>Variations</th><th>Final Amount</th><th>Status</th></tr></thead>
          <tbody>{finalAccounts.map(f => <tr key={f.id}><td>{f.account_no}</td><td>${(f.original_contract_sum||0).toLocaleString()}</td><td>${(f.variation_orders_total||0).toLocaleString()}</td><td>${(f.final_amount||0).toLocaleString()}</td><td>{f.status}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── CDE View ──────────────────────────────────────────────────────────
function CDEView() {
  const [tab, setTab] = useState("submittals");
  const [items, setItems] = useState<any[]>([]);
  const labels: Record<string, string> = { submittals: "Submittals", defects: "Defects", inspections: "Inspections", "site-diaries": "Site Diaries" };

  useEffect(() => {
    api.list<any>(tab).then(setItems).catch(() => {});
  }, [tab]);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Common Data Environment</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {Object.keys(labels).map(k => (
          <button key={k} onClick={() => setTab(k)} className="btn" style={{ background: tab === k ? "var(--amber)" : "transparent", color: tab === k ? "#0c0f1a" : "var(--text)" }}>{labels[k]}</button>
        ))}
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <table><thead><tr><th>ID</th><th>Title</th><th>Status</th></tr></thead>
          <tbody>{items.map(i => <tr key={i.id}><td>#{i.id}</td><td style={{ color: "var(--white)" }}>{i.title || i.defect_no || i.inspection_no || `Diary #${i.id}`}</td><td>{i.status || i.result || i.severity}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Procurement View ──────────────────────────────────────────────────
function ProcurementView() {
  const [tab, setTab] = useState("purchase-requests");
  const [items, setItems] = useState<any[]>([]);
  const labels: Record<string, string> = { "purchase-requests": "Purchase Requests", rfqs: "RFQs", "purchase-orders": "Purchase Orders", "goods-receipts": "Goods Receipts", "e-invoices": "E-Invoices", "cost-codes": "Cost Codes" };

  useEffect(() => {
    api.list<any>(tab).then(setItems).catch(() => {});
  }, [tab]);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Procurement Pipeline</h2>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {Object.keys(labels).map(k => (
          <button key={k} onClick={() => setTab(k)} className="btn" style={{ fontSize: 12, background: tab === k ? "var(--amber)" : "transparent", color: tab === k ? "#0c0f1a" : "var(--text)" }}>{labels[k]}</button>
        ))}
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <table><thead><tr><th>ID</th><th>Title/No</th><th>Status</th><th>Amount</th></tr></thead>
          <tbody>{items.map(i => <tr key={i.id}><td>#{i.id}</td><td style={{ color: "var(--white)" }}>{i.title || i.request_no || i.rfq_no || i.po_number || i.receipt_no || i.invoice_no || i.code}</td><td><span className={`badge badge-${i.status === "Delivered" || i.status === "approved" || i.status === "paid" ? "active" : "pending"}`}>{i.status}</span></td><td>{(i.amount || i.estimated_amount || i.total_amount || 0) > 0 ? `$${(i.amount || i.estimated_amount || i.total_amount).toLocaleString()}` : "—"}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Cost Data View ────────────────────────────────────────────────────
function CostView() {
  const [benchmarks, setBenchmarks] = useState<any[]>([]);
  const [rates, setRates] = useState<any[]>([]);

  useEffect(() => {
    api.list<any>("cost-benchmarks").then(setBenchmarks).catch(() => {});
    api.list<any>("rate-items").then(setRates).catch(() => {});
  }, []);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Cost Data Management</h2>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Cost Benchmarks</h3>
        <table><thead><tr><th>Category</th><th>Unit</th><th>Cost/Unit</th><th>Type</th><th>Region</th></tr></thead>
          <tbody>{benchmarks.map(b => <tr key={b.id}><td>{b.category}</td><td>{b.unit}</td><td>${(b.cost_per_unit||0).toLocaleString()}</td><td>{b.benchmark_type}</td><td>{b.region}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Rate Analysis</h3>
        <table><thead><tr><th>Description</th><th>Unit</th><th>Standard</th><th>Lowest</th><th>Highest</th><th>Average</th></tr></thead>
          <tbody>{rates.map(r => <tr key={r.id}><td>{r.description}</td><td>{r.unit}</td><td>${(r.standard_rate||0).toLocaleString()}</td><td>${(r.lowest_rate||0).toLocaleString()}</td><td>${(r.highest_rate||0).toLocaleString()}</td><td>${(r.average_rate||0).toLocaleString()}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Reports View ──────────────────────────────────────────────────────
function ReportsView() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [reminders, setReminders] = useState<any[]>([]);

  useEffect(() => {
    api.list<any>("report-templates").then(setTemplates).catch(() => {});
    api.list<any>("email-reminders").then(setReminders).catch(() => {});
  }, []);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Reports & Reminders</h2>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Report Templates</h3>
        <table><thead><tr><th>Name</th><th>Type</th><th>Created By</th></tr></thead>
          <tbody>{templates.map(t => <tr key={t.id}><td style={{ color: "var(--white)" }}>{t.name}</td><td>{t.report_type}</td><td>{t.created_by}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Email Reminders</h3>
        <table><thead><tr><th>Entity</th><th>Recipient</th><th>Subject</th><th>Date</th><th>Status</th></tr></thead>
          <tbody>{reminders.map(r => <tr key={r.id}><td>{r.entity_type}</td><td>{r.recipient_email}</td><td>{r.subject}</td><td>{r.reminder_date?.slice(0,10)}</td><td><span className={`badge badge-${r.status === "sent" ? "active" : "pending"}`}>{r.status}</span></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Files View ────────────────────────────────────────────────────────
function FilesView() {
  const [files, setFiles] = useState<any[]>([]);
  const [ocrResult, setOcrResult] = useState<string | null>(null);

  useEffect(() => { api.list<any>("files").then(setFiles).catch(() => {}); }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await api.uploadFile(file);
      const items = await api.list<any>("files");
      setFiles(items);
    } catch (err) { alert(`Upload failed: ${err}`); }
  }

  async function handleOCR(id: number) {
    setOcrResult(null);
    try {
      const result = await api.ocrFile(id) as any;
      setOcrResult(result.text);
    } catch (err) { alert(`OCR failed: ${err}`); }
  }

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Files</h2>
      <input type="file" onChange={handleUpload} style={{ marginBottom: 16 }} />
      {ocrResult && (
        <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
          <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 8 }}>OCR Result</h3>
          <pre style={{ fontSize: 12, whiteSpace: "pre-wrap", color: "var(--text)" }}>{ocrResult}</pre>
        </div>
      )}
      <div className="glass" style={{ padding: 20 }}>
        <table><thead><tr><th>Filename</th><th>Category</th><th>Size</th><th>OCR</th></tr></thead>
          <tbody>{files.map(f => <tr key={f.id}><td style={{ color: "var(--white)" }}>{f.original_filename}</td><td>{f.category}</td><td>{(f.size_bytes/1024).toFixed(1)}KB</td><td><button onClick={() => handleOCR(f.id)} className="btn btn-ghost" style={{ fontSize: 11 }}>Run OCR</button></td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── AI View ───────────────────────────────────────────────────────────
function AIView() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [messages, setMessages] = useState<any[]>([]);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [input, setInput] = useState("");

  useEffect(() => { api.listChatSessions().then(setSessions).catch(() => {}); }, []);

  async function newSession() {
    const s = await api.createChatSession("New Chat");
    setSessions([s, ...sessions]);
    selectSession(s.id);
  }

  async function selectSession(id: number) {
    setSelectedSession(id);
    const msgs = await api.listChatMessages(id);
    setMessages(msgs);
  }

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !selectedSession) return;
    const msg = input;
    setInput("");
    setMessages([...messages, { role: "user", content: msg }]);
    try {
      const reply = await api.sendChatMessage(selectedSession, msg);
      setMessages([...messages, { role: "user", content: msg }, reply]);
    } catch {
      setMessages([...messages, { role: "user", content: msg }, { role: "assistant", content: "Error: AI not available" }]);
    }
  }

  return (
    <div style={{ display: "flex", gap: 16, height: "calc(100vh - 120px)" }}>
      <div className="glass" style={{ width: 200, padding: 16, overflowY: "auto" }}>
        <button onClick={newSession} className="btn btn-primary" style={{ width: "100%", marginBottom: 12 }}>+ New Chat</button>
        {sessions.map(s => (
          <button key={s.id} onClick={() => selectSession(s.id)} className="btn btn-ghost" style={{ width: "100%", textAlign: "left", fontSize: 12, marginBottom: 4, background: selectedSession === s.id ? "rgba(245,158,11,0.1)" : "transparent" }}>{s.title}</button>
        ))}
      </div>
      <div className="glass" style={{ flex: 1, display: "flex", flexDirection: "column", padding: 20 }}>
        <div style={{ flex: 1, overflowY: "auto", marginBottom: 16 }}>
          {messages.map((m, i) => (
            <div key={i} style={{ marginBottom: 12, textAlign: m.role === "user" ? "right" : "left" }}>
              <div style={{ display: "inline-block", maxWidth: "80%", padding: 12, borderRadius: 12, background: m.role === "user" ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.05)", color: "var(--white)", fontSize: 14 }}>{m.content}</div>
            </div>
          ))}
        </div>
        <form onSubmit={sendMessage} style={{ display: "flex", gap: 8 }}>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask ConstructAI..." />
          <button type="submit" className="btn btn-primary">Send</button>
        </form>
      </div>
    </div>
  );
}

// ── Audit View ────────────────────────────────────────────────────────
function AuditView() {
  const [logs, setLogs] = useState<any[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => { api.auditLog(filter || undefined).then(setLogs).catch(() => {}); }, [filter]);

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Audit Log</h2>
      <input placeholder="Filter by entity type..." value={filter} onChange={e => setFilter(e.target.value)} style={{ marginBottom: 16, maxWidth: 300 }} />
      <div className="glass" style={{ padding: 20 }}>
        <table><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Entity</th><th>Summary</th></tr></thead>
          <tbody>{logs.map(l => <tr key={l.id}><td style={{ fontSize: 12 }}>{l.created_at?.slice(0,19)}</td><td>{l.user_email}</td><td><span className={`badge badge-${l.action === "create" ? "active" : l.action === "archive" ? "rejected" : "pending"}`}>{l.action}</span></td><td>{l.entity_type}</td><td>{l.summary}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

// ── Admin View ────────────────────────────────────────────────────────
function AdminView() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [newTenant, setNewTenant] = useState("");

  useEffect(() => {
    api.list<any>("tenants").then(setTenants).catch(() => {});
    api.list<any>("auth/users").then(setUsers).catch(() => {});
  }, []);

  async function createTenant(e: React.FormEvent) {
    e.preventDefault();
    try { await api.create("tenants", { name: newTenant }); setNewTenant(""); api.list<any>("tenants").then(setTenants); } catch (err) { alert(`Error: ${err}`); }
  }

  return (
    <div>
      <h2 style={{ color: "var(--white)", fontSize: 18, marginBottom: 16 }}>Admin</h2>
      <div className="glass" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Tenants</h3>
        <form onSubmit={createTenant} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input placeholder="Tenant name" value={newTenant} onChange={e => setNewTenant(e.target.value)} style={{ maxWidth: 300 }} />
          <button type="submit" className="btn btn-primary">Create</button>
        </form>
        <table><thead><tr><th>ID</th><th>Name</th><th>Created</th></tr></thead>
          <tbody>{tenants.map(t => <tr key={t.id}><td>#{t.id}</td><td style={{ color: "var(--white)" }}>{t.name}</td><td>{t.created_at?.slice(0,10)}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="glass" style={{ padding: 20 }}>
        <h3 style={{ color: "var(--white)", fontSize: 14, marginBottom: 12 }}>Users</h3>
        <table><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Tenant</th><th>Active</th></tr></thead>
          <tbody>{users.map(u => <tr key={u.id}><td>{u.email}</td><td>{u.full_name}</td><td><span className="badge badge-active">{u.role}</span></td><td>{u.tenant_id || "—"}</td><td>{u.is_active ? "✅" : "❌"}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}
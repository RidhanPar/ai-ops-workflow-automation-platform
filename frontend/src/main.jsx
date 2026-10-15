import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Gauge,
  GitBranch,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  RefreshCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Ticket,
  Timer,
  Users,
  Zap,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function api(path, options = {}) {
  const token = localStorage.getItem('aiops_token');
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const err = new Error();
    err.status = response.status;
    const text = await response.text();
    try {
      const parsed = JSON.parse(text);
      const d = parsed.detail;
      if (typeof d === 'string') {
        err.message = d;
      } else if (d && typeof d === 'object') {
        err.message = d.message || JSON.stringify(d);
        err.detail = d;
      } else {
        err.message = `API error ${response.status}`;
      }
    } catch {
      err.message = text || `API error ${response.status}`;
    }
    throw err;
  }
  return response.json();
}

function Login({ onLogin }) {
  const [username, setUsername] = useState(import.meta.env.VITE_DEMO_USERNAME || 'operator');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password }),
      });
      if (!response.ok) {
        setError('Login failed. Use one of the documented demo accounts.');
        return;
      }
      const result = await response.json();
      localStorage.setItem('aiops_token', result.access_token);
      localStorage.setItem('aiops_role', result.role);
      onLogin(result.role);
    } catch {
      setError('Could not reach the server. Please try again in a moment.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-icon"><ShieldCheck size={28} /></div>
        <h1>Secure AI Ops Control Center</h1>
        <p>Sign in to run traceable agent and workflow actions.</p>
        <label>Username<input value={username} onChange={event => setUsername(event.target.value)} disabled={loading} /></label>
        <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} disabled={loading} /></label>
        {error && <div className="toast">{error}</div>}
        <button className="primary login-button" disabled={loading}>
          {loading ? <><RefreshCcw size={16} className="spin" /> Signing in...</> : <><KeyRound size={16} /> Sign in</>}
        </button>
        {loading && (
          <div className="login-loading-note">
            Connecting to server. The free-tier API may take up to 60 seconds
            to wake up on first visit — please wait.
          </div>
        )}
        <small>Local demo credentials are documented in the README.</small>
      </form>
    </div>
  );
}

function StatCard({ title, value, helper, icon: Icon }) {
  return (
    <div className="stat-card">
      <div className="stat-icon"><Icon size={22} /></div>
      <div>
        <p>{title}</p>
        <h2>{value}</h2>
        <span>{helper}</span>
      </div>
    </div>
  );
}

function Badge({ children, type }) {
  return <span className={`badge ${type || ''}`}>{children}</span>;
}

function Section({ title, subtitle, icon: Icon, children, action }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <div className="panel-title"><Icon size={20} /> <h3>{title}</h3></div>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function TicketTable({ tickets, selectedTicketId, onSelect, onAnalyze }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Ticket</th>
            <th>Customer</th>
            <th>Priority</th>
            <th>Status</th>
            <th>Owner</th>
            <th>AI</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map(ticket => (
            <tr key={ticket.id} className={selectedTicketId === ticket.id ? 'selected-row' : ''} onClick={() => onSelect(ticket)}>
              <td>{ticket.external_id}</td>
              <td>
                <strong>{ticket.title}</strong>
                <small>{ticket.category} · {ticket.channel}</small>
              </td>
              <td>{ticket.customer}</td>
              <td><Badge type={ticket.priority}>{ticket.priority}</Badge></td>
              <td><Badge type={ticket.status}>{ticket.status.replace('_', ' ')}</Badge></td>
              <td>{ticket.owner?.name || 'Unassigned'}</td>
              <td>
                <button className="mini-button" onClick={(event) => { event.stopPropagation(); onAnalyze(ticket.id); }}>
                  Analyze
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WorkflowList({ workflows }) {
  return (
    <div className="workflow-grid">
      {workflows.map(workflow => (
        <div className="workflow-card" key={workflow.id}>
          <div className="workflow-top">
            <GitBranch size={18} />
            <Badge type={workflow.enabled ? 'enabled' : 'disabled'}>{workflow.enabled ? 'enabled' : 'disabled'}</Badge>
          </div>
          <h4>{workflow.name}</h4>
          <p>{workflow.description}</p>
          <div className="workflow-code">
            <span>Trigger: {Object.keys(workflow.trigger).join(', ')}</span>
            <span>Actions: {workflow.actions.map(a => a.type).join(' → ')}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Risk Review helpers ───────────────────────────────────────────────────────

function getUsername() {
  try {
    const token = localStorage.getItem('aiops_token');
    if (!token) return null;
    return JSON.parse(atob(token.split('.')[1])).sub;
  } catch { return null; }
}

const SOURCE_LABELS = {
  openai_structured_output: 'OpenAI structured output',
  anthropic_messages: 'Anthropic tool use',
  fallback_no_provider: 'Fallback — no LLM configured',
  fallback_invalid_output: 'Fallback — invalid LLM output',
  fallback_provider_failure: 'Fallback — LLM provider error',
  fallback_unexpected_failure: 'Fallback — unexpected error',
  seed: 'Pre-seeded',
};

function scoreType(score) {
  if (score >= 20) return 'critical';
  if (score >= 12) return 'high';
  if (score >= 6) return 'medium';
  return 'low';
}

function sourceVariant(source) {
  if (source === 'openai_structured_output' || source === 'anthropic_messages') return 'enabled';
  if (source === 'seed') return '';
  return 'high';
}

function RiskReviewPage({ role }) {
  const [risks, setRisks] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [latestPkg, setLatestPkg] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pkgLoading, setPkgLoading] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [toast, setToast] = useState('');
  const [createForm, setCreateForm] = useState({
    title: '', description: '', business_unit: '', owner: '',
    impact: 3, likelihood: 3, proposed_mitigation: '',
  });
  const [assessForm, setAssessForm] = useState({ perspective: 'security', vote: 'mitigate', comment: '' });
  const [assessLoading, setAssessLoading] = useState(false);
  const [decisionForm, setDecisionForm] = useState({ decision: 'mitigate', rationale: '' });
  const [decisionLoading, setDecisionLoading] = useState(false);

  const currentUser = getUsername();
  const canWrite = ['operator', 'manager', 'admin'].includes(role);
  const canDecide = ['manager', 'admin'].includes(role);
  const selectedRisk = risks.find(r => r.id === selectedId) || null;

  async function loadRisks() {
    setLoading(true);
    try {
      const data = await api('/risks');
      setRisks(data);
    } catch (e) { setToast(e.message); }
    finally { setLoading(false); }
  }

  async function loadPackage(riskId) {
    if (!riskId) return;
    setPkgLoading(true);
    setLatestPkg(null);
    try {
      const pkg = await api(`/risks/${riskId}/latest-package`);
      setLatestPkg(pkg);
    } catch (e) {
      if (e.status !== 404) setToast(e.message);
    } finally { setPkgLoading(false); }
  }

  useEffect(() => { loadRisks(); }, []);
  useEffect(() => { loadPackage(selectedId); }, [selectedId]);

  const filtered = useMemo(
    () => statusFilter === 'all' ? risks : risks.filter(r => r.status === statusFilter),
    [risks, statusFilter]
  );

  async function handleCreate(e) {
    e.preventDefault();
    try {
      const risk = await api('/risks', {
        method: 'POST',
        body: JSON.stringify({
          ...createForm,
          impact: Number(createForm.impact),
          likelihood: Number(createForm.likelihood),
          proposed_mitigation: createForm.proposed_mitigation || null,
        }),
      });
      setShowCreate(false);
      setCreateForm({ title: '', description: '', business_unit: '', owner: '', impact: 3, likelihood: 3, proposed_mitigation: '' });
      await loadRisks();
      setSelectedId(risk.id);
    } catch (e) { setToast(e.message); }
  }

  async function handleGeneratePackage() {
    if (!selectedId) return;
    setGenLoading(true);
    try {
      const pkg = await api(`/risks/${selectedId}/decision-package`, {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
      });
      setLatestPkg(pkg);
      await loadRisks();
      setToast('Package generated.');
    } catch (e) {
      if (e.detail?.gaps) {
        setToast(`Incomplete: ${e.detail.gaps.join('; ')}`);
      } else {
        setToast(e.message);
      }
      await loadPackage(selectedId);
    } finally { setGenLoading(false); }
  }

  async function handleAssess(e) {
    e.preventDefault();
    if (!latestPkg) return;
    setAssessLoading(true);
    try {
      await api(`/decision-packages/${latestPkg.id}/assessments`, {
        method: 'POST',
        body: JSON.stringify(assessForm),
      });
      setAssessForm({ perspective: 'security', vote: 'mitigate', comment: '' });
      await loadPackage(selectedId);
      setToast('Assessment submitted.');
    } catch (e) { setToast(e.message); }
    finally { setAssessLoading(false); }
  }

  async function handleDecide(e) {
    e.preventDefault();
    if (!selectedRisk || !latestPkg) return;
    setDecisionLoading(true);
    try {
      await api(`/risks/${selectedRisk.id}/decision`, {
        method: 'POST',
        body: JSON.stringify({
          ...decisionForm,
          decision_package_id: latestPkg.id,
          version: selectedRisk.version,
        }),
      });
      setDecisionForm({ decision: 'mitigate', rationale: '' });
      await loadRisks();
      await loadPackage(selectedId);
      setToast('Decision recorded.');
    } catch (e) {
      setToast(e.detail?.message || e.message);
    } finally { setDecisionLoading(false); }
  }

  const qualifyingAssessments = useMemo(
    () => (latestPkg?.assessments || []).filter(a => a.reviewer !== currentUser),
    [latestPkg, currentUser]
  );
  const alreadyAssessed = useMemo(
    () => (latestPkg?.assessments || []).some(a => a.reviewer === currentUser),
    [latestPkg, currentUser]
  );

  const assessBlockReason = !latestPkg ? 'No package yet'
    : latestPkg.needs_info ? 'Package is incomplete — fix and regenerate'
    : selectedRisk?.status === 'decided' ? 'Risk is already decided'
    : alreadyAssessed ? 'You have already submitted an assessment for this package'
    : null;

  const decideBlockReason = !latestPkg || latestPkg.needs_info ? 'No valid package'
    : selectedRisk?.status === 'decided' ? 'Risk is already decided'
    : qualifyingAssessments.length < 2 ? `Need ${2 - qualifyingAssessments.length} more qualifying assessment(s) (yours excluded)`
    : null;

  return (
    <div>
      {toast && <div className="toast" onClick={() => setToast('')}>{toast}</div>}
      <div className="dashboard-grid two-one" style={{ alignItems: 'start' }}>
        {/* ── Left: Risk list ── */}
        <Section title="Risk Register" subtitle={`${risks.length} risks · ${risks.filter(r => r.status === 'in_review').length} in review`} icon={ShieldAlert}
          action={canWrite && <button className="primary" style={{ fontSize: 13, padding: '6px 14px' }} onClick={() => setShowCreate(s => !s)}>+ New Risk</button>}
        >
          <div className="risk-list-header">
            <div className="filter-tabs">
              {['all', 'draft', 'in_review', 'decided'].map(s => (
                <button key={s} className={`filter-tab${statusFilter === s ? ' active' : ''}`} onClick={() => setStatusFilter(s)}>
                  {s === 'all' ? 'All' : s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
          {showCreate && (
            <div className="form-block" style={{ marginBottom: 16 }}>
              <h5>New Risk Item</h5>
              <form className="risk-form" onSubmit={handleCreate}>
                <div className="row-2">
                  <label>Title<input required minLength={5} value={createForm.title} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} /></label>
                  <label>Business Unit<input required value={createForm.business_unit} onChange={e => setCreateForm(f => ({ ...f, business_unit: e.target.value }))} /></label>
                </div>
                <label>Description<textarea required minLength={10} value={createForm.description} onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))} /></label>
                <div className="row-2">
                  <label>Owner<input required value={createForm.owner} onChange={e => setCreateForm(f => ({ ...f, owner: e.target.value }))} /></label>
                  <label>Proposed Mitigation<input value={createForm.proposed_mitigation} onChange={e => setCreateForm(f => ({ ...f, proposed_mitigation: e.target.value }))} placeholder="Optional — required for package generation" /></label>
                </div>
                <div className="row-2">
                  <label>Impact (1–5)<input type="number" min={1} max={5} value={createForm.impact} onChange={e => setCreateForm(f => ({ ...f, impact: e.target.value }))} /></label>
                  <label>Likelihood (1–5)<input type="number" min={1} max={5} value={createForm.likelihood} onChange={e => setCreateForm(f => ({ ...f, likelihood: e.target.value }))} /></label>
                </div>
                <div className="form-actions">
                  <button type="button" onClick={() => setShowCreate(false)}>Cancel</button>
                  <button type="submit" className="primary">Create Risk</button>
                </div>
              </form>
            </div>
          )}
          {loading ? <p style={{ color: '#64748b', padding: '16px 0' }}>Loading risks…</p> : (
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>Title</th><th>Owner</th><th>Status</th><th>Score</th></tr></thead>
                <tbody>
                  {filtered.map(risk => {
                    const score = risk.impact * risk.likelihood;
                    return (
                      <tr key={risk.id} className={selectedId === risk.id ? 'selected-row' : ''} onClick={() => setSelectedId(risk.id)} style={{ cursor: 'pointer' }}>
                        <td>
                          <strong>{risk.title}</strong>
                          <small>{risk.business_unit}</small>
                        </td>
                        <td>{risk.owner}</td>
                        <td><Badge type={risk.status}>{risk.status.replace('_', ' ')}</Badge></td>
                        <td><Badge type={scoreType(score)}>{score}/25</Badge></td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 && <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b', padding: 16 }}>No risks match this filter.</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {/* ── Right: Risk detail ── */}
        <div style={{ display: 'grid', gap: 16 }}>
          {!selectedRisk ? (
            <div className="panel"><p className="no-package">Select a risk from the list to view details.</p></div>
          ) : (
            <>
              {/* Meta header */}
              <div className="panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{ margin: '0 0 6px', fontSize: 16 }}>{selectedRisk.title}</h3>
                    <p style={{ margin: '0 0 10px', fontSize: 13, color: '#64748b' }}>{selectedRisk.description}</p>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge type={selectedRisk.status}>{selectedRisk.status.replace('_', ' ')}</Badge>
                      <Badge type={scoreType(selectedRisk.impact * selectedRisk.likelihood)}>Score {selectedRisk.impact * selectedRisk.likelihood}/25</Badge>
                      <span style={{ fontSize: 12, color: '#64748b' }}>BU: {selectedRisk.business_unit} · Owner: {selectedRisk.owner}</span>
                    </div>
                  </div>
                  {canWrite && selectedRisk.status !== 'decided' && (
                    <button className="primary" style={{ fontSize: 13, padding: '7px 14px', whiteSpace: 'nowrap' }} onClick={handleGeneratePackage} disabled={genLoading}>
                      {genLoading ? 'Generating…' : 'Generate Package'}
                    </button>
                  )}
                </div>
                {selectedRisk.proposed_mitigation && (
                  <p style={{ margin: '10px 0 0', fontSize: 13 }}><strong>Proposed mitigation:</strong> {selectedRisk.proposed_mitigation}</p>
                )}
              </div>

              {/* Package detail */}
              <div className="panel">
                {pkgLoading ? (
                  <p style={{ color: '#64748b', textAlign: 'center', padding: '20px 0' }}>Loading package…</p>
                ) : !latestPkg ? (
                  <p className="no-package">No decision package yet. Click "Generate Package" to start the review.</p>
                ) : latestPkg.needs_info ? (
                  <div>
                    <div className="needs-info-banner">
                      <h5>Incomplete risk item</h5>
                      <p style={{ margin: '4px 0 8px', fontSize: 13 }}>
                        This package could not be fully generated because required fields are missing.
                        Fix the gaps below and click "Generate Package" again with a new key.
                      </p>
                      <ul className="gaps-list">
                        {latestPkg.completeness_gaps.map((g, i) => <li key={i}>{g}</li>)}
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="score-row">
                      <span style={{ fontWeight: 700, fontSize: 14 }}>Risk Package</span>
                      <Badge type={scoreType(latestPkg.risk_score)}>Score {latestPkg.risk_score}/25</Badge>
                      <Badge type={latestPkg.recommended_treatment}>{latestPkg.recommended_treatment}</Badge>
                    </div>
                    <div className="source-bar">
                      <Badge type={sourceVariant(latestPkg.source)}>{SOURCE_LABELS[latestPkg.source] || latestPkg.source}</Badge>
                      <span style={{ color: '#64748b', fontSize: 12 }}>Trace: {latestPkg.trace_id?.slice(0, 12)}</span>
                    </div>
                    {latestPkg.safety_flags?.length > 0 && (
                      <div className="pkg-section">
                        <h5>Safety Flags</h5>
                        <div className="safety-flags">
                          {latestPkg.safety_flags.map((f, i) => <span key={i} className="safety-flag">{f}</span>)}
                        </div>
                      </div>
                    )}
                    <div className="pkg-section">
                      <h5>Perspectives</h5>
                      <div className="perspectives-grid">
                        {(latestPkg.perspectives || []).map((p, i) => (
                          <div key={i} className="perspective-card">
                            <h5>
                              <Badge type={p.area}>{p.area}</Badge>
                            </h5>
                            <p style={{ fontWeight: 700, fontSize: 12, margin: '4px 0 2px', color: '#334155' }}>Key concerns</p>
                            <ul>{p.key_concerns?.map((c, j) => <li key={j}>{c}</li>)}</ul>
                            <p style={{ fontWeight: 700, fontSize: 12, margin: '8px 0 2px', color: '#334155' }}>Reviewer questions</p>
                            <ul>{p.reviewer_questions?.map((q, j) => <li key={j}>{q}</li>)}</ul>
                            <div className="p-footer">
                              <Badge type={p.suggested_treatment}>{p.suggested_treatment}</Badge>
                              <span>Confidence: {Math.round((p.confidence || 0) * 100)}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    {latestPkg.best_practices?.length > 0 && (
                      <div className="pkg-section">
                        <h5>Cited Best Practice Documents</h5>
                        <div className="cited-list">
                          {latestPkg.best_practices.map((doc, i) => (
                            <div key={i} className="cited-item">
                              <strong>{doc.title}</strong>
                              <span>{(doc.content || '').slice(0, 200)}{doc.content?.length > 200 ? '…' : ''}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {latestPkg.past_decisions?.length > 0 && (
                      <div className="pkg-section">
                        <h5>Cited Past Decisions</h5>
                        <div className="cited-list">
                          {latestPkg.past_decisions.map((pd, i) => (
                            <div key={i} className="cited-item">
                              <strong>{pd.risk_title}</strong>
                              <span><Badge type={pd.decision}>{pd.decision}</Badge></span>
                              <span style={{ fontSize: 12, color: '#64748b', marginTop: 4, display: 'block' }}>{(pd.rationale || '').slice(0, 200)}{pd.rationale?.length > 200 ? '…' : ''}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Assessments */}
                    <div className="pkg-section">
                      <h5>Assessments ({latestPkg.assessments?.length || 0})</h5>
                      {latestPkg.assessments?.length > 0 ? (
                        <div className="assess-list">
                          {latestPkg.assessments.map(a => (
                            <div key={a.id} className="assess-row">
                              <div className="assess-meta">
                                <strong>{a.reviewer}{a.reviewer === currentUser ? ' (you)' : ''}</strong>
                                <span>{a.comment}</span>
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
                                <Badge type={a.perspective}>{a.perspective}</Badge>
                                <Badge type={a.vote}>{a.vote}</Badge>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : <p style={{ color: '#64748b', fontSize: 13 }}>No assessments yet.</p>}
                    </div>
                  </div>
                )}

                {/* Assessment form */}
                <div className="form-block">
                  <h5>Submit Assessment</h5>
                  {assessBlockReason ? (
                    <p className="disabled-reason">{assessBlockReason}</p>
                  ) : (
                    <form className="risk-form" onSubmit={handleAssess}>
                      <div className="row-2">
                        <label>Perspective
                          <select value={assessForm.perspective} onChange={e => setAssessForm(f => ({ ...f, perspective: e.target.value }))}>
                            <option value="security">Security</option>
                            <option value="compliance">Compliance</option>
                            <option value="business">Business</option>
                          </select>
                        </label>
                        <label>Vote
                          <select value={assessForm.vote} onChange={e => setAssessForm(f => ({ ...f, vote: e.target.value }))}>
                            <option value="accept">Accept</option>
                            <option value="mitigate">Mitigate</option>
                            <option value="transfer">Transfer</option>
                            <option value="reject">Reject</option>
                          </select>
                        </label>
                      </div>
                      <label>Comment (min 10 chars)
                        <textarea required minLength={10} value={assessForm.comment} onChange={e => setAssessForm(f => ({ ...f, comment: e.target.value }))} />
                      </label>
                      <div className="form-actions">
                        <button type="submit" className="primary" disabled={assessLoading}>{assessLoading ? 'Submitting…' : 'Submit Assessment'}</button>
                      </div>
                    </form>
                  )}
                </div>

                {/* Decision form — manager/admin only */}
                {canDecide && (
                  <div className="form-block">
                    <h5>Record Decision</h5>
                    <p className="qual-count">
                      Qualifying assessments: <strong>{qualifyingAssessments.length}</strong> / 2 required
                      {currentUser && <span style={{ fontSize: 12, color: '#64748b' }}> (your own assessment as deciding manager is excluded)</span>}
                    </p>
                    {decideBlockReason ? (
                      <p className="disabled-reason">{decideBlockReason}</p>
                    ) : (
                      <form className="risk-form" onSubmit={handleDecide}>
                        <div className="row-2">
                          <label>Decision
                            <select value={decisionForm.decision} onChange={e => setDecisionForm(f => ({ ...f, decision: e.target.value }))}>
                              <option value="accept">Accept</option>
                              <option value="mitigate">Mitigate</option>
                              <option value="transfer">Transfer</option>
                              <option value="avoid">Avoid</option>
                            </select>
                          </label>
                        </div>
                        <label>Rationale (min 20 chars)
                          <textarea required minLength={20} value={decisionForm.rationale} onChange={e => setDecisionForm(f => ({ ...f, rationale: e.target.value }))} />
                        </label>
                        <div className="form-actions">
                          <button type="submit" className="primary" disabled={decisionLoading}>{decisionLoading ? 'Recording…' : 'Record Decision'}</button>
                        </div>
                      </form>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [overview, setOverview] = useState(null);
  const [trends, setTrends] = useState([]);
  const [backlog, setBacklog] = useState({ by_status: [], by_priority: [], by_category: [] });
  const [workforce, setWorkforce] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [aiResult, setAiResult] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [role, setRole] = useState(localStorage.getItem('aiops_role'));
  const [traces, setTraces] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [page, setPage] = useState('dashboard');

  async function loadData() {
    setLoading(true);
    try {
      const [overviewData, trendsData, backlogData, workforceData, ticketsData, workflowsData, tracesData, approvalsData] = await Promise.all([
        api('/kpis/overview'),
        api('/kpis/trends'),
        api('/kpis/backlog'),
        api('/kpis/workforce'),
        api('/tickets'),
        api('/workflows'),
        api('/observability/traces'),
        api('/governance/approvals'),
      ]);
      setOverview(overviewData);
      setTrends(trendsData);
      setBacklog(backlogData);
      setWorkforce(workforceData);
      setTickets(ticketsData);
      setWorkflows(workflowsData);
      setTraces(tracesData);
      setApprovals(approvalsData);
      setSelectedTicket(ticketsData[0] || null);
    } catch (error) {
      if (error.status === 401) { localStorage.clear(); setRole(null); return; }
      setToast(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (role) loadData(); }, [role]);

  const filteredTickets = useMemo(() => {
    const value = search.toLowerCase();
    if (!value) return tickets;
    return tickets.filter(ticket =>
      ticket.title.toLowerCase().includes(value)
      || ticket.customer.toLowerCase().includes(value)
      || ticket.external_id.toLowerCase().includes(value)
      || ticket.category.toLowerCase().includes(value)
    );
  }, [tickets, search]);

  async function analyzeTicket(ticketId) {
    setToast('Running AI ticket analysis...');
    try {
      const result = await api('/ai/analyze-ticket', {
        method: 'POST',
        body: JSON.stringify({ ticket_id: ticketId, allow_write_tools: true }),
      });
      setAiResult(result);
      setToast('AI analysis completed.');
      await loadData();
    } catch (error) {
      if (error.status === 401) { localStorage.clear(); setRole(null); return; }
      setToast(error.message);
    }
  }

  async function runAutomation() {
    setToast('Running workflow automation rules...');
    try {
      const result = await api('/workflows/run', {
        method: 'POST',
        body: JSON.stringify({ ticket_id: selectedTicket?.id || null, idempotency_key: crypto.randomUUID() }),
      });
      setToast(`${result.executions.length} workflow execution(s) completed.`);
      await loadData();
    } catch (error) {
      if (error.status === 401) { localStorage.clear(); setRole(null); return; }
      setToast(error.message);
    }
  }

  if (!role) {
    return <Login onLogin={setRole} />;
  }

  async function downloadReport() {
    const token = localStorage.getItem('aiops_token');
    const response = await fetch(`${API_BASE}/reports/powerbi/tickets.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      setToast('Could not download the protected report.');
      return;
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'powerbi_tickets_export.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  if (loading && !overview) {
    return <div className="loading">Loading AI operations platform...</div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Zap size={24} /></div>
          <div>
            <h1>AI Ops</h1>
            <p>Workflow Automation</p>
          </div>
        </div>
        <nav>
          <a className={page === 'dashboard' ? 'active' : ''} onClick={() => setPage('dashboard')}><LayoutDashboard size={18} /> Dashboard</a>
          <a className={page === 'tickets' ? 'active' : ''} onClick={() => setPage('tickets')}><Ticket size={18} /> Tickets</a>
          <a className={page === 'workflows' ? 'active' : ''} onClick={() => setPage('workflows')}><GitBranch size={18} /> Workflows</a>
          <a className={page === 'ai' ? 'active' : ''} onClick={() => setPage('ai')}><Bot size={18} /> AI Assistant</a>
          <a className={page === 'workforce' ? 'active' : ''} onClick={() => setPage('workforce')}><Users size={18} /> Workforce</a>
          <a className={page === 'risks' ? 'active' : ''} onClick={() => setPage('risks')}><ShieldAlert size={18} /> Risk Review</a>
        </nav>
        <div className="side-card">
          <p>Power BI Dataset</p>
          <button onClick={downloadReport}>Download protected CSV</button>
        </div>
      </aside>

      <main>
        <header className="hero">
          <div>
            <Badge type="live">Live Ops Control Center</Badge>
            <h2>AI Ops — Workflow Automation for HR, Finance and Operations</h2>
            <p>Monitor SLA risk, automate ticket routing, summarize issues with AI, and track support operations performance in one place.</p>
          </div>
          <div className="hero-actions">
            <Badge type="enabled">{role}</Badge>
            <button onClick={loadData}><RefreshCcw size={16} /> Refresh</button>
            <button className="primary" onClick={runAutomation}><Zap size={16} /> Run Automation</button>
            <button onClick={() => { localStorage.clear(); setRole(null); }}><KeyRound size={16} /> Sign out</button>
          </div>
        </header>

        {toast && <div className="toast">{toast}</div>}

        {/* ── DASHBOARD ── */}
        {page === 'dashboard' && <>
          <div className="stats-grid">
            <StatCard title="Total Tickets" value={overview?.total_tickets ?? 0} helper="All support cases" icon={Ticket} />
            <StatCard title="Open Backlog" value={overview?.open_tickets ?? 0} helper="Unresolved workload" icon={Gauge} />
            <StatCard title="SLA At Risk" value={overview?.sla_at_risk ?? 0} helper="Needs attention" icon={AlertTriangle} />
            <StatCard title="Resolved" value={overview?.resolved_tickets ?? 0} helper="Completed cases" icon={CheckCircle2} />
          </div>

          <div className="dashboard-grid">
            <Section title="Ticket Volume Trend" subtitle="Created vs resolved tickets over the last 14 days" icon={LayoutDashboard}>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trends}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Area dataKey="created" type="monotone" fillOpacity={0.2} />
                  <Line dataKey="resolved" type="monotone" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </Section>

            <Section title="Backlog by Priority" subtitle="Operational risk distribution" icon={AlertTriangle}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={backlog.by_priority}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Section>
          </div>

          <div className="dashboard-grid two-one">
            <Section title="Ticket Queue" subtitle="Search, select, and analyze operational tickets" icon={Ticket} action={
              <div className="search-box"><Search size={16} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tickets..." /></div>
            }>
              <TicketTable tickets={filteredTickets} selectedTicketId={selectedTicket?.id} onSelect={setSelectedTicket} onAnalyze={analyzeTicket} />
            </Section>

            <Section title="AI Ticket Assistant" subtitle="Summary and next best action" icon={Bot}>
              {aiResult ? (
                <div className="ai-card">
                  <h4>{aiResult.summary}</h4>
                  <p><strong>Category:</strong> {aiResult.category}</p>
                  <p><strong>Priority:</strong> {aiResult.recommended_priority}</p>
                  <p><strong>Team:</strong> {aiResult.recommended_team}</p>
                  <p><strong>Next action:</strong> {aiResult.next_action}</p>
                  <p><strong>Tools:</strong> {aiResult.tools_used?.join(' → ')}</p>
                  <p><strong>Knowledge:</strong> {aiResult.knowledge_sources?.join(', ') || 'No match'}</p>
                  <small>Confidence: {Math.round(aiResult.confidence * 100)}% · {aiResult.latency_ms} ms · Trace: {aiResult.trace_id}</small>
                </div>
              ) : selectedTicket ? (
                <div className="ai-card empty">
                  <h4>{selectedTicket.title}</h4>
                  <p>{selectedTicket.ai_summary || 'Click Analyze on any ticket to generate AI summary and recommended next action.'}</p>
                  {selectedTicket.ai_next_action && <p><strong>Next action:</strong> {selectedTicket.ai_next_action}</p>}
                </div>
              ) : <p>No ticket selected.</p>}
            </Section>
          </div>

          <div className="dashboard-grid">
            <Section title="Agent & Workflow Traces" subtitle="Latest persisted execution telemetry" icon={Timer}>
              <div className="trace-list">
                {traces.slice(0, 8).map((trace, index) => (
                  <div className="trace-row" key={`${trace.trace_id}-${index}`}>
                    <div><strong>{trace.name}</strong><small>{trace.type} · {trace.trace_id.slice(0, 12)}</small></div>
                    <Badge type={trace.status === 'success' ? 'enabled' : 'critical'}>{trace.status}</Badge>
                    <span>{Math.round(trace.latency_ms)} ms</span>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Human Approval Queue" subtitle="Sensitive actions stay reviewable and reversible" icon={ListChecks}>
              <div className="trace-list">
                {approvals.slice(0, 8).map(approval => (
                  <div className="trace-row" key={approval.id}>
                    <div><strong>{approval.action_type}</strong><small>Ticket {approval.ticket_id} · {approval.requested_by}</small></div>
                    <Badge type={approval.status === 'pending' ? 'high' : 'enabled'}>{approval.status}</Badge>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <div className="dashboard-grid">
            <Section title="Workflow Automation Rules" subtitle="rule-based trigger and action automation" icon={GitBranch}>
              <WorkflowList workflows={workflows} />
            </Section>

            <Section title="Workforce Productivity" subtitle="Agent workload and operational capacity" icon={Users}>
              <div className="table-wrap compact">
                <table>
                  <thead>
                    <tr><th>Agent</th><th>Team</th><th>Active</th><th>Score</th></tr>
                  </thead>
                  <tbody>
                    {workforce.map(row => (
                      <tr key={row.agent}>
                        <td><strong>{row.agent}</strong><small>{row.skill}</small></td>
                        <td>{row.team}</td>
                        <td>{row.active_tickets}</td>
                        <td>{row.productivity_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie data={backlog.by_status} dataKey="value" nameKey="name" outerRadius={75} label>
                    {backlog.by_status.map((_, index) => <Cell key={index} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Section>
          </div>
        </>}

        {/* ── TICKETS ── */}
        {page === 'tickets' && <>
          <div className="stats-grid">
            <StatCard title="Total Tickets" value={overview?.total_tickets ?? 0} helper="All support cases" icon={Ticket} />
            <StatCard title="Open Backlog" value={overview?.open_tickets ?? 0} helper="Unresolved workload" icon={Gauge} />
            <StatCard title="SLA At Risk" value={overview?.sla_at_risk ?? 0} helper="Needs attention" icon={AlertTriangle} />
            <StatCard title="Resolved" value={overview?.resolved_tickets ?? 0} helper="Completed cases" icon={CheckCircle2} />
          </div>
          <div className="dashboard-grid two-one">
            <Section title="Ticket Queue" subtitle="Search, select, and analyze operational tickets" icon={Ticket} action={
              <div className="search-box"><Search size={16} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tickets..." /></div>
            }>
              <TicketTable tickets={filteredTickets} selectedTicketId={selectedTicket?.id} onSelect={setSelectedTicket} onAnalyze={analyzeTicket} />
            </Section>
            <Section title="AI Ticket Assistant" subtitle="Summary and next best action" icon={Bot}>
              {aiResult ? (
                <div className="ai-card">
                  <h4>{aiResult.summary}</h4>
                  <p><strong>Category:</strong> {aiResult.category}</p>
                  <p><strong>Priority:</strong> {aiResult.recommended_priority}</p>
                  <p><strong>Team:</strong> {aiResult.recommended_team}</p>
                  <p><strong>Next action:</strong> {aiResult.next_action}</p>
                  <p><strong>Tools:</strong> {aiResult.tools_used?.join(' → ')}</p>
                  <p><strong>Knowledge:</strong> {aiResult.knowledge_sources?.join(', ') || 'No match'}</p>
                  <small>Confidence: {Math.round(aiResult.confidence * 100)}% · {aiResult.latency_ms} ms · Trace: {aiResult.trace_id}</small>
                </div>
              ) : selectedTicket ? (
                <div className="ai-card empty">
                  <h4>{selectedTicket.title}</h4>
                  <p>{selectedTicket.ai_summary || 'Click Analyze on any ticket to generate AI summary and recommended next action.'}</p>
                  {selectedTicket.ai_next_action && <p><strong>Next action:</strong> {selectedTicket.ai_next_action}</p>}
                </div>
              ) : <p>No ticket selected.</p>}
            </Section>
          </div>
          <div className="dashboard-grid">
            <Section title="Human Approval Queue" subtitle="Sensitive actions stay reviewable and reversible" icon={ListChecks}>
              <div className="trace-list">
                {approvals.slice(0, 12).map(approval => (
                  <div className="trace-row" key={approval.id}>
                    <div><strong>{approval.action_type}</strong><small>Ticket {approval.ticket_id} · {approval.requested_by}</small></div>
                    <Badge type={approval.status === 'pending' ? 'high' : 'enabled'}>{approval.status}</Badge>
                  </div>
                ))}
              </div>
            </Section>
            <Section title="Agent & Workflow Traces" subtitle="Latest persisted execution telemetry" icon={Timer}>
              <div className="trace-list">
                {traces.slice(0, 12).map((trace, index) => (
                  <div className="trace-row" key={`${trace.trace_id}-${index}`}>
                    <div><strong>{trace.name}</strong><small>{trace.type} · {trace.trace_id.slice(0, 12)}</small></div>
                    <Badge type={trace.status === 'success' ? 'enabled' : 'critical'}>{trace.status}</Badge>
                    <span>{Math.round(trace.latency_ms)} ms</span>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </>}

        {/* ── WORKFLOWS ── */}
        {page === 'workflows' && <>
          <Section title="Workflow Automation Rules" subtitle="rule-based trigger and action automation engine" icon={GitBranch}>
            <WorkflowList workflows={workflows} />
          </Section>
          <div className="dashboard-grid">
            <Section title="Human Approval Queue" subtitle="Sensitive workflow actions pending review" icon={ListChecks}>
              <div className="trace-list">
                {approvals.slice(0, 12).map(approval => (
                  <div className="trace-row" key={approval.id}>
                    <div><strong>{approval.action_type}</strong><small>Ticket {approval.ticket_id} · {approval.requested_by}</small></div>
                    <Badge type={approval.status === 'pending' ? 'high' : 'enabled'}>{approval.status}</Badge>
                  </div>
                ))}
              </div>
            </Section>
            <Section title="Agent & Workflow Traces" subtitle="Latest persisted execution telemetry" icon={Timer}>
              <div className="trace-list">
                {traces.slice(0, 12).map((trace, index) => (
                  <div className="trace-row" key={`${trace.trace_id}-${index}`}>
                    <div><strong>{trace.name}</strong><small>{trace.type} · {trace.trace_id.slice(0, 12)}</small></div>
                    <Badge type={trace.status === 'success' ? 'enabled' : 'critical'}>{trace.status}</Badge>
                    <span>{Math.round(trace.latency_ms)} ms</span>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </>}

        {/* ── AI ASSISTANT ── */}
        {page === 'ai' && <>
          <div className="dashboard-grid two-one">
            <Section title="Ticket Queue" subtitle="Select a ticket then click Analyze" icon={Ticket} action={
              <div className="search-box"><Search size={16} /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tickets..." /></div>
            }>
              <TicketTable tickets={filteredTickets} selectedTicketId={selectedTicket?.id} onSelect={setSelectedTicket} onAnalyze={analyzeTicket} />
            </Section>
            <Section title="AI Ticket Assistant" subtitle="LangGraph agent analysis and recommended action" icon={Bot}>
              {aiResult ? (
                <div className="ai-card">
                  <h4>{aiResult.summary}</h4>
                  <p><strong>Category:</strong> {aiResult.category}</p>
                  <p><strong>Priority:</strong> {aiResult.recommended_priority}</p>
                  <p><strong>Team:</strong> {aiResult.recommended_team}</p>
                  <p><strong>Next action:</strong> {aiResult.next_action}</p>
                  <p><strong>Tools:</strong> {aiResult.tools_used?.join(' → ')}</p>
                  <p><strong>Knowledge:</strong> {aiResult.knowledge_sources?.join(', ') || 'No match'}</p>
                  <small>Confidence: {Math.round(aiResult.confidence * 100)}% · {aiResult.latency_ms} ms · Trace: {aiResult.trace_id}</small>
                </div>
              ) : selectedTicket ? (
                <div className="ai-card empty">
                  <h4>{selectedTicket.title}</h4>
                  <p>{selectedTicket.ai_summary || 'Click Analyze on any ticket row to run the LangGraph agent.'}</p>
                  {selectedTicket.ai_next_action && <p><strong>Next action:</strong> {selectedTicket.ai_next_action}</p>}
                </div>
              ) : <p>No ticket selected.</p>}
            </Section>
          </div>
          <Section title="Agent Traces" subtitle="Persisted LangGraph execution spans" icon={Timer}>
            <div className="trace-list">
              {traces.filter(t => t.type === 'agent').slice(0, 15).map((trace, index) => (
                <div className="trace-row" key={`${trace.trace_id}-${index}`}>
                  <div><strong>{trace.name}</strong><small>{trace.type} · {trace.trace_id.slice(0, 12)}</small></div>
                  <Badge type={trace.status === 'success' ? 'enabled' : 'critical'}>{trace.status}</Badge>
                  <span>{Math.round(trace.latency_ms)} ms</span>
                </div>
              ))}
            </div>
          </Section>
        </>}

        {/* ── WORKFORCE ── */}
        {page === 'workforce' && <>
          <div className="stats-grid">
            <StatCard title="Total Tickets" value={overview?.total_tickets ?? 0} helper="All support cases" icon={Ticket} />
            <StatCard title="Open Backlog" value={overview?.open_tickets ?? 0} helper="Unresolved workload" icon={Gauge} />
            <StatCard title="SLA At Risk" value={overview?.sla_at_risk ?? 0} helper="Needs attention" icon={AlertTriangle} />
            <StatCard title="Resolved" value={overview?.resolved_tickets ?? 0} helper="Completed cases" icon={CheckCircle2} />
          </div>
          <div className="dashboard-grid">
            <Section title="Workforce Productivity" subtitle="Agent workload and operational capacity" icon={Users}>
              <div className="table-wrap compact">
                <table>
                  <thead>
                    <tr><th>Agent</th><th>Team</th><th>Active</th><th>Score</th></tr>
                  </thead>
                  <tbody>
                    {workforce.map(row => (
                      <tr key={row.agent}>
                        <td><strong>{row.agent}</strong><small>{row.skill}</small></td>
                        <td>{row.team}</td>
                        <td>{row.active_tickets}</td>
                        <td>{row.productivity_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
            <Section title="Backlog by Status" subtitle="Current workload distribution" icon={AlertTriangle}>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie data={backlog.by_status} dataKey="value" nameKey="name" outerRadius={110} label>
                    {backlog.by_status.map((_, index) => <Cell key={index} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Section>
          </div>
          <div className="dashboard-grid">
            <Section title="Backlog by Priority" subtitle="Operational risk distribution" icon={AlertTriangle}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={backlog.by_priority}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Section>
            <Section title="Backlog by Category" subtitle="Support issue category breakdown" icon={LayoutDashboard}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={backlog.by_category}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Section>
          </div>
        </>}

        {/* ── RISK REVIEW ── */}
        {page === 'risks' && <RiskReviewPage role={role} />}

      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);

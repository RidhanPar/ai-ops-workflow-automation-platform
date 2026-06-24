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
      err.message = JSON.parse(text).detail || `API error ${response.status}`;
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

  async function submit(event) {
    event.preventDefault();
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
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-icon"><ShieldCheck size={28} /></div>
        <h1>Secure AI Ops Control Center</h1>
        <p>Sign in to run traceable agent and workflow actions.</p>
        <label>Username<input value={username} onChange={event => setUsername(event.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} /></label>
        {error && <div className="toast">{error}</div>}
        <button className="primary login-button"><KeyRound size={16} /> Sign in</button>
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
            <h2>AI Operations & Workflow Automation Platform</h2>
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
            <Section title="Workflow Automation Rules" subtitle="n8n-inspired trigger and action automation" icon={GitBranch}>
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
          <Section title="Workflow Automation Rules" subtitle="n8n-inspired trigger and action automation engine" icon={GitBranch}>
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

      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Mail, Clock, Zap,
  RefreshCw, ArrowDown, ArrowUp, ShieldAlert, MessageSquare,
  CheckCircle, AlertCircle
} from 'lucide-react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip as RechartsTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  LineChart, Line
} from 'recharts'
import { GetGmailAnalyticsService, GetEmailAccountsService } from '../services/ApiService'

// ─── Shared color scheme — MUST match GmailIntegration.jsx LABEL_CONFIG ──────

const LABEL_COLORS = {
  Sales:         '#10b981',   // emerald-500
  Support:       '#3b82f6',   // blue-500
  Grievance:     '#ef4444',   // red-500
  Transactional: '#9ca3af',   // gray-400
  Promotional:   '#8b5cf6',   // purple-500
  Personal:      '#ec4899',   // pink-500
  Unclassified:  '#6b7280',   // gray-500
}

const STATUS_COLORS = {
  new:           '#3b82f6',   // blue
  classified:    '#9ca3af',   // gray
  draft_ready:   '#f59e0b',   // amber
  pending_human: '#ef4444',   // red
  replied:       '#10b981',   // emerald
  archived:      '#6b7280',   // gray
  ignored:       '#d1d5db',   // light gray
}

const STATUS_LABELS = {
  new:           'New',
  classified:    'Classified',
  draft_ready:   'Draft Ready',
  pending_human: 'Needs Review',
  replied:       'Replied',
  archived:      'Archived',
  ignored:       'Ignored',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmt(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString()
}

function StatCard({ icon: Icon, label, value, sub, color, loading }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 flex items-start gap-4">
      <div className="p-2.5 rounded-xl flex-shrink-0" style={{ background: `${color}18` }}>
        <Icon size={18} style={{ color }} />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wide mb-0.5">{label}</p>
        {loading
          ? <div className="h-6 w-20 bg-gray-100 rounded animate-pulse" />
          : <p className="text-xl font-bold text-gray-900">{value}</p>}
        {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  )
}

function ResolutionBar({ label, total, resolved, pending, color }) {
  const resolvedPct = total ? Math.round((resolved / total) * 100) : 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-gray-700">{label}</span>
        <span className="text-gray-400">{resolved} / {total} resolved</span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${resolvedPct}%`, background: color }} />
      </div>
      <div className="flex gap-4 text-[11px]">
        <span className="flex items-center gap-1 text-emerald-600">
          <CheckCircle size={10} /> {resolved} resolved ({resolvedPct}%)
        </span>
        <span className="flex items-center gap-1 text-red-500">
          <AlertCircle size={10} /> {pending} pending
        </span>
      </div>
    </div>
  )
}

const TOOLTIP_STYLE = { borderRadius: 10, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', fontSize: 12 }

// ─── Main ─────────────────────────────────────────────────────────────────────

const TIME_RANGES = [
  { key: '7h',  label: 'Last 7h' },
  { key: '24h', label: 'Last 24h' },
  { key: '48h', label: 'Last 48h' },
  { key: '7d',  label: 'Last 7 days' },
  { key: 'all', label: 'All time' },
]

export default function GmailAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [since, setSince] = useState('7d')
  const [accounts, setAccounts] = useState([])
  const [activeAccount, setActiveAccount] = useState('')

  useEffect(() => {
    GetEmailAccountsService(
      (res) => setAccounts(res?.items || []),
      () => {}
    )
  }, [])

  const load = (s = since, acc = activeAccount) => {
    setLoading(true)
    GetGmailAnalyticsService(
      s,
      acc || null,
      (res) => { setData(res); setLoading(false) },
      () => setLoading(false)
    )
  }

  useEffect(() => { load(since, activeAccount) }, [since, activeAccount])

  const labelData = data
    ? Object.entries(data.by_label || {}).map(([name, value]) => ({ name, value })).filter(d => d.value > 0)
    : []

  const statusData = data
    ? Object.entries(data.by_status || {})
        .map(([key, value]) => ({ name: STATUS_LABELS[key] || key, key, value }))
        .filter(d => d.value > 0)
    : []

  const autoSentPct = data?.auto_sent_rate_pct ?? 0
  // sla_met + sla_breached = all Sales emails whose 2h window has expired (the eligible set)
  const slaTotal = (data?.sla_met ?? 0) + (data?.sla_breached ?? 0)
  const slaMetPct = slaTotal ? Math.round(((data?.sla_met ?? 0) / slaTotal) * 100) : 0
  const slaColor = slaMetPct >= 80 ? '#10b981' : slaMetPct >= 50 ? '#f59e0b' : '#ef4444'

  const dailyData = data?.daily_stats || []

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-gray-100 p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Email Analytics
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">Pipeline performance, SLA compliance, and label breakdown</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {/* Account selector */}
            {accounts.length > 1 && (
              <select
                value={activeAccount}
                onChange={e => setActiveAccount(e.target.value)}
                className="text-xs border border-gray-200 rounded-xl px-3 py-2 bg-white text-gray-700 shadow-sm focus:outline-none focus:border-indigo-400">
                <option value="">All accounts</option>
                {accounts.map(a => (
                  <option key={a.id} value={a.id}>
                    {a.email_address}{a.is_primary ? ' ★' : ''}
                  </option>
                ))}
              </select>
            )}
            {/* Time range selector */}
            <div className="flex items-center bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
              {TIME_RANGES.map(({ key, label }) => (
                <button key={key} onClick={() => setSince(key)}
                  className={`px-3 py-2 text-xs font-semibold transition-all whitespace-nowrap
                    ${since === key
                      ? 'bg-indigo-600 text-white'
                      : 'text-gray-500 hover:bg-gray-50'}`}>
                  {label}
                </button>
              ))}
            </div>
            <button onClick={() => load(since, activeAccount)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all text-sm font-medium text-gray-600">
              <RefreshCw size={14} className={loading ? 'animate-spin text-indigo-500' : ''} />
              Refresh
            </button>
          </div>
        </div>

        {/* Period badge — shown under every section */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Showing data for:</span>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100">
            {TIME_RANGES.find(r => r.key === since)?.label}
          </span>
          <span className="text-[10px] text-gray-400">(daily chart always shows last 14 days)</span>
        </div>

        {/* Volume KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Mail}      label="Total Emails"  value={fmt(data?.total_emails)}       color="#6172f3" loading={loading} />
          <StatCard icon={ArrowDown} label="Inbound"       value={fmt(data?.total_inbound)}       color="#3b82f6" loading={loading} sub="Received from customers" />
          <StatCard icon={ArrowUp}   label="Outbound"      value={fmt(data?.total_outbound)}      color="#10b981" loading={loading} sub="Sent by AI + team" />
          <StatCard icon={Zap}       label="Sales Emails"  value={fmt(data?.total_sales_emails)}  color="#10b981" loading={loading} sub="Auto-processed" />
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Zap}           label="Auto-Sent Rate"      value={loading ? '—' : `${autoSentPct}%`}                      color="#10b981" loading={loading} sub="No human touch needed" />
          <StatCard icon={Clock}         label="Avg Reply Time"       value={loading ? '—' : `${data?.avg_reply_minutes ?? 0} min`}   color="#f59e0b" loading={loading} sub="Sales emails only" />
          <StatCard icon={ShieldAlert}   label="SLA Compliance"       value={loading ? '—' : `${slaMetPct}%`}                        color={slaColor} loading={loading} sub={`${data?.sla_met ?? 0} met · ${data?.sla_breached ?? 0} breached`} />
          <StatCard icon={MessageSquare} label="Competitor Mentions"  value={fmt(data?.competitor_mentions)}                          color="#ef4444" loading={loading} />
        </div>

        {/* Daily Volume Chart */}
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-1">
            Email Volume
            <span className="ml-2 text-[11px] font-normal text-gray-400">
              {since === 'all' ? '(weekly buckets · full history)' :
               since === '7h' ? '(hourly · last 7h)' :
               since === '24h' ? '(2-hour buckets · last 24h)' :
               since === '48h' ? '(4-hour buckets · last 48h)' :
               '(daily · last 7 days)'}
            </span>
          </h2>
          {loading ? (
            <div className="h-52 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
          ) : dailyData.length === 0 ? (
            <div className="h-52 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={dailyData} margin={{ left: 0, right: 8, bottom: 0 }} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} />
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="inbound"  name="Inbound"  fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={18} />
                <Bar dataKey="outbound" name="Outbound" fill="#10b981" radius={[3, 3, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* SLA Trend + Resolution Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* SLA Daily Trend */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-1">SLA Performance — Last 14 Days</h2>
            <p className="text-[11px] text-gray-400 mb-4">Sales emails answered within 2h</p>
            {loading ? (
              <div className="h-44 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : (
              <ResponsiveContainer width="100%" height={170}>
                <LineChart data={dailyData} margin={{ left: 0, right: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="sla_met"      name="SLA Met"     stroke="#10b981" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="sla_breached" name="SLA Breached" stroke="#ef4444" strokeWidth={2} dot={false} strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
            )}
            {/* SLA Summary bar */}
            <div className="mt-4 space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Overall SLA — {slaTotal} emails tracked</span>
                <span className="font-semibold" style={{ color: slaColor }}>{slaMetPct}% within 2h</span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${slaMetPct}%`, background: slaColor }} />
              </div>
              <div className="flex gap-4 text-[11px]">
                <span className="flex items-center gap-1 text-emerald-600"><CheckCircle size={10} /> {data?.sla_met ?? 0} met</span>
                <span className="flex items-center gap-1 text-red-500"><AlertCircle size={10} /> {data?.sla_breached ?? 0} breached</span>
              </div>
            </div>
          </div>

          {/* Grievance + Support Resolution */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-5">Support & Grievance Resolution</h2>
            {loading ? (
              <div className="h-44 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : (
              <div className="space-y-6">
                <ResolutionBar
                  label="Grievance"
                  total={data?.grievance_total ?? 0}
                  resolved={data?.grievance_resolved ?? 0}
                  pending={data?.grievance_pending ?? 0}
                  color={LABEL_COLORS.Grievance}
                />
                <ResolutionBar
                  label="Support"
                  total={data?.support_total ?? 0}
                  resolved={data?.support_resolved ?? 0}
                  pending={data?.support_pending ?? 0}
                  color={LABEL_COLORS.Support}
                />

                {/* Mini metric tiles */}
                <div className="grid grid-cols-2 gap-3 pt-2">
                  {[
                    { label: 'Grievance Pending', value: data?.grievance_pending ?? 0, color: '#ef4444' },
                    { label: 'Support Pending',   value: data?.support_pending   ?? 0, color: '#3b82f6' },
                    { label: 'Grievance Resolved',value: data?.grievance_resolved ?? 0, color: '#10b981' },
                    { label: 'Support Resolved',  value: data?.support_resolved  ?? 0, color: '#10b981' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="text-center p-3 rounded-xl bg-gray-50">
                      <p className="text-xl font-bold" style={{ color }}>{fmt(value)}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Pipeline Status + Classification */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* Status bar chart — vertical bars, compact */}
          <div className="lg:col-span-2 glass-card p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Pipeline Status</h2>
            {loading ? (
              <div className="h-40 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : statusData.length === 0 ? (
              <div className="h-40 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={statusData} margin={{ left: 0, right: 4, bottom: 28 }} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#9ca3af' }} axisLine={false} tickLine={false} interval={0} angle={-35} textAnchor="end" />
                  <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} width={24} />
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="value" name="Count" radius={[4, 4, 0, 0]} maxBarSize={28}>
                    {statusData.map((entry) => (
                      <Cell key={entry.key} fill={STATUS_COLORS[entry.key] || '#9ca3af'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Label pie — bigger */}
          <div className="lg:col-span-3 glass-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Email Classification by Label</h2>
            {loading ? (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : labelData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
            ) : (
              <div className="flex gap-6 items-center">
                <div className="flex-shrink-0" style={{ width: 220 }}>
                  <ResponsiveContainer width={220} height={220}>
                    <PieChart>
                      <Pie data={labelData} cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={2} dataKey="value">
                        {labelData.map((entry) => (
                          <Cell key={entry.name} fill={LABEL_COLORS[entry.name] || '#9ca3af'} />
                        ))}
                      </Pie>
                      <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 space-y-2">
                  {labelData.sort((a, b) => b.value - a.value).map(({ name, value }) => {
                    const total = labelData.reduce((s, d) => s + d.value, 0)
                    const p = total ? Math.round(value / total * 100) : 0
                    const color = LABEL_COLORS[name] || '#9ca3af'
                    return (
                      <div key={name} className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="text-xs text-gray-600 flex-1">{name}</span>
                        <div className="w-20 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${p}%`, background: color }} />
                        </div>
                        <span className="text-xs font-semibold text-gray-800 w-6 text-right">{value}</span>
                        <span className="text-[10px] text-gray-400 w-7 text-right">{p}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Sales Pipeline detail */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <h2 className="text-sm font-semibold text-gray-900">Sales Pipeline Metrics</h2>
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 border border-indigo-100">
              {TIME_RANGES.find(r => r.key === since)?.label}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Auto-Sent',           value: data?.auto_sent,            color: '#10b981', sub: 'No human needed' },
              { label: 'Drafted for Review',  value: data?.drafted_for_review,   color: '#f59e0b', sub: 'Had knowledge gaps' },
              { label: 'Pending Human',       value: data?.pending_human,         color: '#ef4444', sub: 'Support / Grievance' },
              { label: 'SLA Breaches',        value: data?.sla_breached,          color: slaColor,  sub: '>2h without reply' },
            ].map(({ label, value, color, sub }) => (
              <div key={label} className="text-center p-4 rounded-xl bg-gray-50">
                <p className="text-2xl font-bold" style={{ color }}>{loading ? '—' : fmt(value)}</p>
                <p className="text-xs font-semibold text-gray-700 mt-1">{label}</p>
                <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Mail, Send, AlertTriangle, Clock, Zap, Users,
  TrendingUp, RefreshCw, ArrowDown, ArrowUp, ShieldAlert, MessageSquare
} from 'lucide-react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip as RechartsTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend
} from 'recharts'
import { GetGmailAnalyticsService } from '../services/ApiService'

// ─── Config ──────────────────────────────────────────────────────────────────

const LABEL_COLORS = {
  Sales:         '#10b981',
  Support:       '#f59e0b',
  Grievance:     '#ef4444',
  Transactional: '#3b82f6',
  Promotional:   '#8b5cf6',
  Personal:      '#ec4899',
  Unclassified:  '#9ca3af',
}

const STATUS_COLORS = {
  new:           '#6172f3',
  classified:    '#9ca3af',
  draft_ready:   '#f59e0b',
  pending_human: '#ef4444',
  replied:       '#10b981',
  archived:      '#6b7280',
  ignored:       '#d1d5db',
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
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 flex items-start gap-4"
    >
      <div className="p-2.5 rounded-xl flex-shrink-0" style={{ background: `${color}18` }}>
        <Icon size={18} style={{ color }} />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wide mb-0.5">{label}</p>
        {loading ? (
          <div className="h-6 w-20 bg-gray-100 rounded animate-pulse" />
        ) : (
          <p className="text-xl font-bold text-gray-900">{value}</p>
        )}
        {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  )
}

const CustomPieLabel = ({ cx, cy, midAngle, outerRadius, percent, name }) => {
  if (percent < 0.05) return null
  const RADIAN = Math.PI / 180
  const r = outerRadius + 24
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="#6b7280" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={11} fontWeight={500}>
      {name} ({(percent * 100).toFixed(0)}%)
    </text>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function GmailAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    GetGmailAnalyticsService(
      (res) => { setData(res); setLoading(false) },
      () => setLoading(false)
    )
  }

  useEffect(() => { load() }, [])

  const labelData = data
    ? Object.entries(data.by_label || {}).map(([name, value]) => ({ name, value }))
    : []

  const statusData = data
    ? Object.entries(data.by_status || {})
        .map(([key, value]) => ({ name: STATUS_LABELS[key] || key, key, value }))
        .filter(d => d.value > 0)
    : []

  const directionData = data
    ? [
        { name: 'Inbound', value: data.total_inbound || 0, color: '#6172f3' },
        { name: 'Outbound', value: data.total_outbound || 0, color: '#10b981' },
      ]
    : []

  const autoSentPct = data?.auto_sent_rate_pct ?? 0
  const slaColor = (data?.sla_breached || 0) === 0 ? '#10b981' : '#ef4444'

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-gray-100 p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Email Analytics
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">Pipeline performance, SLA compliance, and label breakdown</p>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all text-sm font-medium text-gray-600"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin text-indigo-500' : ''} />
            Refresh
          </button>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Mail}         label="Total Emails"     value={fmt(data?.total_emails)}           color="#6172f3" loading={loading} />
          <StatCard icon={ArrowDown}    label="Inbound"          value={fmt(data?.total_inbound)}          color="#3b82f6" loading={loading} sub="Received from customers" />
          <StatCard icon={ArrowUp}      label="Outbound"         value={fmt(data?.total_outbound)}         color="#10b981" loading={loading} sub="Sent by your team" />
          <StatCard icon={Users}        label="Sales Emails"     value={fmt(data?.total_sales_emails)}     color="#8b5cf6" loading={loading} />
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Zap}          label="Auto-Sent Rate"   value={loading ? '—' : `${autoSentPct}%`}                     color="#10b981" loading={loading} sub="No human touch needed" />
          <StatCard icon={Clock}        label="Avg Reply Time"   value={loading ? '—' : `${data?.avg_reply_minutes ?? 0} min`}  color="#f59e0b" loading={loading} sub="Sales emails only" />
          <StatCard icon={ShieldAlert}  label="SLA Breaches"     value={fmt(data?.sla_breached)}           color={slaColor}  loading={loading} sub=">2h unresolved Sales" />
          <StatCard icon={MessageSquare} label="Competitor Mentions" value={fmt(data?.competitor_mentions)} color="#ef4444"  loading={loading} />
        </div>

        {/* Pipeline Status + Direction row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Pipeline Status bar chart */}
          <div className="lg:col-span-2 glass-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-5">Pipeline Status Breakdown</h2>
            {loading ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : statusData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={statusData} layout="vertical" margin={{ left: 8, right: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} width={90} />
                  <RechartsTooltip
                    contentStyle={{ borderRadius: 10, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', fontSize: 12 }}
                  />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={28}>
                    {statusData.map((entry) => (
                      <Cell key={entry.key} fill={STATUS_COLORS[entry.key] || '#9ca3af'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Inbound vs Outbound donut */}
          <div className="glass-card p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-5">Direction Split</h2>
            {loading ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
            ) : (data?.total_emails || 0) === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">No emails yet</div>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie data={directionData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                      {directionData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      contentStyle={{ borderRadius: 10, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex justify-center gap-5 mt-2">
                  {directionData.map(d => (
                    <div key={d.name} className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                      <span className="text-xs text-gray-500">{d.name} <span className="font-semibold text-gray-800">{d.value}</span></span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Label Breakdown */}
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-5">Email Classification Breakdown</h2>
          {loading ? (
            <div className="h-56 flex items-center justify-center text-gray-400 text-sm">Loading...</div>
          ) : labelData.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-gray-400 text-sm">No data yet</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={labelData}
                    cx="50%" cy="50%"
                    outerRadius={85}
                    paddingAngle={2}
                    dataKey="value"
                    labelLine={false}
                    label={CustomPieLabel}
                  >
                    {labelData.map((entry) => (
                      <Cell key={entry.name} fill={LABEL_COLORS[entry.name] || '#9ca3af'} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{ borderRadius: 10, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Legend table */}
              <div className="space-y-2">
                {labelData
                  .sort((a, b) => b.value - a.value)
                  .map(({ name, value }) => {
                    const total = labelData.reduce((s, d) => s + d.value, 0)
                    const pct = total ? Math.round(value / total * 100) : 0
                    const color = LABEL_COLORS[name] || '#9ca3af'
                    return (
                      <div key={name} className="flex items-center gap-3">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="text-xs text-gray-600 flex-1">{name}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                          </div>
                          <span className="text-xs font-semibold text-gray-800 w-8 text-right">{value}</span>
                          <span className="text-[10px] text-gray-400 w-8 text-right">{pct}%</span>
                        </div>
                      </div>
                    )
                  })}
              </div>
            </div>
          )}
        </div>

        {/* SLA Detail */}
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Sales Pipeline Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Auto-Sent',        value: data?.auto_sent,           color: '#10b981', sub: 'No human needed' },
              { label: 'Drafted for Review', value: data?.drafted_for_review, color: '#f59e0b', sub: 'Had knowledge gaps' },
              { label: 'Pending Human',    value: data?.pending_human,        color: '#ef4444', sub: 'Support/Grievance' },
              { label: 'SLA Breaches',     value: data?.sla_breached,         color: slaColor,  sub: '>2h without reply' },
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

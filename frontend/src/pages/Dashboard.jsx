import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Target, Phone, Mail, BrainCircuit, TrendingUp,
  ArrowUpRight, CheckCircle, AlertCircle, Clock,
  Layers, Star, Zap, Users,
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, Cell, PieChart, Pie, Legend,
} from 'recharts'
import {
  GetDealAnalyticsService,
  GetGmailAnalyticsService,
  GetCallAnalyticsService,
  GetAIAnalyticsService,
  GetLeadClassificationSummaryService,
} from '../services/ApiService'

const tooltipStyle = {
  contentStyle: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

const STAGE_COLORS = {
  'New': '#6172f3',
  'Qualified': '#8b5cf6',
  'Proposal': '#f59e0b',
  'Negotiation': '#f97316',
  'Closed Won': '#10b981',
  'Closed Lost': '#ef4444',
}
const TIER_COLORS = { HIGH: '#10b981', MEDIUM: '#f59e0b', LOW: '#ef4444', UNCLASSIFIED: '#94a3b8' }
const PIE_COLORS = ['#6172f3', '#10b981', '#f59e0b', '#f97316', '#ef4444', '#94a3b8']

function fmt(n, prefix = '') {
  if (n === null || n === undefined) return '—'
  if (n >= 1_000_000) return `${prefix}${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${prefix}${(n / 1_000).toFixed(1)}K`
  return `${prefix}${Number(n).toLocaleString()}`
}

function KpiCard({ icon: Icon, label, value, sub, color, to }) {
  const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-100' },
    green: { bg: 'bg-emerald-50', text: 'text-emerald-600', ring: 'ring-emerald-100' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-600', ring: 'ring-purple-100' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', ring: 'ring-orange-100' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-600', ring: 'ring-cyan-100' },
  }
  const c = colorMap[color] || colorMap.blue
  return (
    <div className="glass-card p-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${c.bg} ring-1 ${c.ring}`}>
        <Icon size={18} className={c.text} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide truncate">{label}</p>
        <p className="text-xl font-bold text-gray-900 leading-tight">{value}</p>
        {sub && <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
      {to && (
        <Link to={to} className="flex-shrink-0 text-gray-300 hover:text-blue-500 transition-colors">
          <ArrowUpRight size={15} />
        </Link>
      )}
    </div>
  )
}

function SectionHeader({ title, sub, to, toLabel = 'View details' }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
      {to && (
        <Link to={to} className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors">
          {toLabel} <ArrowUpRight size={12} />
        </Link>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [deal, setDeal] = useState(null)
  const [email, setEmail] = useState(null)
  const [calls, setCalls] = useState(null)
  const [ai, setAi] = useState(null)
  const [leads, setLeads] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      new Promise(r => GetDealAnalyticsService(r, () => r(null))),
      new Promise(r => GetGmailAnalyticsService('7d', null, r, () => r(null))),
      new Promise(r => GetCallAnalyticsService(r, () => r(null))),
      new Promise(r => GetAIAnalyticsService(r, () => r(null))),
      new Promise(r => GetLeadClassificationSummaryService(r, () => r(null))),
    ]).then(([d, e, c, a, l]) => {
      setDeal(d); setEmail(e); setCalls(c); setAi(a); setLeads(l)
      setLoading(false)
    })
  }, [])

  // ── derived values ────────────────────────────────────────────────────────
  const pipelineValue = deal?.total_open_value ?? null
  const winRate = deal?.win_rate ?? null
  const totalEmails = email?.total_emails ?? null
  const autoSentRate = email?.auto_sent_rate ?? null
  const totalCalls = calls?.total_calls ?? null
  const callConverted = calls?.by_outcome?.converted ?? null
  const aiQueries = ai?.total_queries ?? null
  const avgLatency = ai?.avg_latency_ms ? `${(ai.avg_latency_ms / 1000).toFixed(1)}s` : null
  const highLeads = leads?.tiers?.HIGH?.count ?? null

  const kpis = [
    { icon: Layers, label: 'Open Pipeline', value: fmt(pipelineValue, '₹'), sub: `${deal?.open_deals ?? '—'} open deals`, color: 'blue', to: '/dashboard' },
    { icon: TrendingUp, label: 'Win Rate', value: winRate !== null ? `${winRate}%` : '—', sub: `${deal?.total_won ?? '—'} deals closed won`, color: 'green', to: '/dashboard' },
    { icon: Mail, label: 'Emails Processed', value: fmt(totalEmails), sub: autoSentRate !== null ? `${autoSentRate}% auto-sent` : null, color: 'purple', to: '/gmail-analytics' },
    { icon: Phone, label: 'Total Calls', value: fmt(totalCalls), sub: callConverted !== null ? `${callConverted} converted` : null, color: 'orange', to: '/calls' },
    { icon: BrainCircuit, label: 'AI Queries', value: fmt(aiQueries), sub: avgLatency ? `avg ${avgLatency}` : null, color: 'cyan', to: '/ai-analytics' },
  ]

  // ── chart data ─────────────────────────────────────────────────────────────
  const stageData = deal?.by_stage
    ? Object.entries(deal.by_stage)
        .filter(([, v]) => v.count > 0)
        .map(([stage, v]) => ({ stage, count: v.count, value: v.total_value }))
    : []

  const revenueData = deal?.revenue
    ? [
        { period: 'Last Month', value: deal.revenue.last_month },
        { period: 'This Month', value: deal.revenue.this_month },
        { period: 'This Quarter', value: deal.revenue.this_quarter },
        { period: 'YTD', value: deal.revenue.ytd },
      ]
    : []

  const emailLabelData = email?.by_label
    ? Object.entries(email.by_label)
        .filter(([, v]) => v > 0)
        .map(([label, count], i) => ({ name: label, value: count, fill: PIE_COLORS[i % PIE_COLORS.length] }))
    : []

  const tierItems = leads?.tiers
    ? Object.entries(leads.tiers).map(([tier, data]) => ({
        label: tier,
        count: data.count ?? 0,
        avg: data.avg_score ? Math.round(data.avg_score) : 0,
        color: TIER_COLORS[tier] ?? '#94a3b8',
      }))
    : []

  const totalLeads = tierItems.reduce((s, t) => s + t.count, 0)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="space-y-6"
    >
      {/* ── KPI strip ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {kpis.map((kpi, i) => (
          <motion.div key={kpi.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <KpiCard {...kpi} />
          </motion.div>
        ))}
      </div>

      {loading && <p className="text-center text-xs text-gray-400">Loading live data…</p>}

      {/* ── Row 1: Pipeline by stage + Revenue ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Pipeline by stage */}
        <div className="lg:col-span-2 glass-card p-5">
          <SectionHeader title="Pipeline by Stage" sub="Open deal count per stage" to="/dashboard" toLabel="Full pipeline" />
          {stageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220} minWidth={0}>
              <BarChart data={stageData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="35%">
                <CartesianGrid stroke="rgba(0,0,0,0.05)" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="stage" tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip {...tooltipStyle} formatter={(v, n) => [v, n === 'count' ? 'Deals' : 'Value']} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} name="count">
                  {stageData.map(entry => (
                    <Cell key={entry.stage} fill={STAGE_COLORS[entry.stage] ?? '#6172f3'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-xs text-gray-400 py-10 text-center">No deal data yet.</p>
          )}
        </div>

        {/* Revenue by period */}
        <div className="glass-card p-5">
          <SectionHeader title="Revenue Won" sub="Closed Won deal value" />
          {revenueData.length > 0 ? (
            <div className="space-y-3 mt-1">
              {revenueData.map((r, i) => {
                const max = Math.max(...revenueData.map(x => x.value), 1)
                const pct = Math.round((r.value / max) * 100)
                return (
                  <div key={r.period}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">{r.period}</span>
                      <span className="text-xs font-bold text-gray-900">{fmt(r.value, '₹')}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <motion.div
                        className="h-full rounded-full bg-emerald-500"
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                      />
                    </div>
                  </div>
                )
              })}

              {/* Avg cycle + velocity */}
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-2 gap-3">
                <div className="text-center">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide">Avg Cycle</p>
                  <p className="text-base font-bold text-gray-900">{deal?.avg_sales_cycle_days ?? '—'}<span className="text-[10px] font-normal text-gray-400"> days</span></p>
                </div>
                <div className="text-center">
                  <p className="text-[10px] text-gray-400 uppercase tracking-wide">Velocity</p>
                  <p className="text-base font-bold text-gray-900">{fmt(deal?.pipeline_velocity, '₹')}<span className="text-[10px] font-normal text-gray-400">/day</span></p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400 py-10 text-center">No closed deals yet.</p>
          )}
        </div>
      </div>

      {/* ── Row 2: Email labels + Lead tiers + AI/Calls mini ────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Email label breakdown */}
        <div className="glass-card p-5">
          <SectionHeader title="Email Classification" sub="Inbound by label" to="/gmail-analytics" />
          {emailLabelData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180} minWidth={0}>
              <PieChart>
                <Pie data={emailLabelData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={65} paddingAngle={2}>
                  {emailLabelData.map(entry => <Cell key={entry.name} fill={entry.fill} />)}
                </Pie>
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-xs text-gray-400 py-10 text-center">No email data yet.</p>
          )}

          {/* SLA + auto-sent summary */}
          {email && (
            <div className="mt-2 flex justify-between text-center border-t border-gray-100 pt-3">
              <div>
                <p className="text-[10px] text-gray-400">Auto-sent</p>
                <p className="text-sm font-bold text-emerald-600">{email.auto_sent_rate ?? '—'}%</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">SLA Breaches</p>
                <p className="text-sm font-bold text-red-500">{email.sla_breaches ?? '—'}</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">Avg Reply</p>
                <p className="text-sm font-bold text-gray-900">{email.avg_reply_time_minutes ? `${Math.round(email.avg_reply_time_minutes)}m` : '—'}</p>
              </div>
            </div>
          )}
        </div>

        {/* Lead classification tiers */}
        <div className="glass-card p-5">
          <SectionHeader title="Lead Classification" sub="By engagement tier" to="/leads" />
          {tierItems.length > 0 ? (
            <div className="space-y-3">
              {tierItems.map((tier, i) => {
                const pct = totalLeads > 0 ? Math.round((tier.count / totalLeads) * 100) : 0
                return (
                  <div key={tier.label}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: tier.color }} />
                        <span className="text-xs text-gray-600 font-medium">{tier.label}</span>
                      </div>
                      <div className="flex items-center gap-2 text-right">
                        <span className="text-[10px] text-gray-400">avg {tier.avg}</span>
                        <span className="text-xs font-bold text-gray-900 w-5 text-right">{tier.count}</span>
                      </div>
                    </div>
                    <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ background: tier.color }}
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                      />
                    </div>
                  </div>
                )
              })}
              <div className="pt-3 border-t border-gray-100 flex justify-between text-center">
                <div>
                  <p className="text-[10px] text-gray-400">Total Leads</p>
                  <p className="text-sm font-bold text-gray-900">{totalLeads}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400">HIGH</p>
                  <p className="text-sm font-bold text-emerald-600">{leads?.tiers?.HIGH?.count ?? '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400">At Risk</p>
                  <p className="text-sm font-bold text-red-500">{leads?.tiers?.LOW?.count ?? '—'}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400 py-10 text-center">No lead data yet.</p>
          )}
        </div>

        {/* AI + Calls quick stats */}
        <div className="glass-card p-5 flex flex-col gap-4">
          <SectionHeader title="AI & Calls" sub="Quick metrics" />

          {/* AI stats */}
          <div className="rounded-xl bg-purple-50/60 border border-purple-100 p-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <BrainCircuit size={13} className="text-purple-600" />
              <span className="text-xs font-semibold text-purple-700">AI / RAG</span>
              <Link to="/ai-analytics" className="ml-auto text-[10px] text-purple-500 hover:text-purple-700 flex items-center gap-0.5">Details <ArrowUpRight size={10} /></Link>
            </div>
            {[
              { label: 'Total Queries', value: fmt(ai?.total_queries) },
              { label: 'Avg Latency', value: ai?.avg_latency_ms ? `${(ai.avg_latency_ms / 1000).toFixed(1)}s` : '—' },
              { label: 'Est. Cost', value: ai?.total_cost ? `$${Number(ai.total_cost).toFixed(4)}` : '—' },
            ].map(r => (
              <div key={r.label} className="flex justify-between">
                <span className="text-[10px] text-gray-500">{r.label}</span>
                <span className="text-[10px] font-bold text-gray-900">{r.value}</span>
              </div>
            ))}
          </div>

          {/* Call stats */}
          <div className="rounded-xl bg-orange-50/60 border border-orange-100 p-4 space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <Phone size={13} className="text-orange-600" />
              <span className="text-xs font-semibold text-orange-700">Calls</span>
              <Link to="/calls" className="ml-auto text-[10px] text-orange-500 hover:text-orange-700 flex items-center gap-0.5">Details <ArrowUpRight size={10} /></Link>
            </div>
            {[
              { label: 'Total Calls', value: fmt(calls?.total_calls) },
              { label: 'Inbound', value: fmt(calls?.by_direction?.inbound) },
              { label: 'Converted', value: fmt(calls?.by_outcome?.converted) },
              { label: 'Avg Duration', value: calls?.avg_duration_minutes ? `${Number(calls.avg_duration_minutes).toFixed(1)}m` : '—' },
            ].map(r => (
              <div key={r.label} className="flex justify-between">
                <span className="text-[10px] text-gray-500">{r.label}</span>
                <span className="text-[10px] font-bold text-gray-900">{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

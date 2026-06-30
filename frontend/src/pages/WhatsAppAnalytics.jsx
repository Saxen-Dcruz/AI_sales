import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip as RechartsTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import {
  MessageCircle, TrendingUp, ShieldAlert, Zap, Clock,
  Users, CheckCircle, AlertCircle, BarChart2,
  RefreshCw, Package, ChevronRight
} from 'lucide-react'
import { GetWhatsAppAnalyticsService, GetWhatsAppConversationService } from '../services/ApiService'

// ── Color palettes ─────────────────────────────────────────────────────────────
const WA_GREEN   = '#25D366'
const WA_DARK    = '#128C7E'

const LABEL_COLORS = {
  Sales:         '#25D366',
  Support:       '#3b82f6',
  Grievance:     '#ef4444',
  Transactional: '#6b7280',
  Promotional:   '#8b5cf6',
  Personal:      '#ec4899',
  Unclassified:  '#d1d5db',
}

const STATUS_COLORS = {
  new:           '#3b82f6',
  classified:    '#6b7280',
  draft_ready:   '#f59e0b',
  pending_human: '#ef4444',
  replied:       '#25D366',
  archived:      '#9ca3af',
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

const TOOLTIP_STYLE = {
  borderRadius: 10, border: 'none',
  boxShadow: '0 4px 20px rgba(0,0,0,0.10)', fontSize: 12
}

const TABS = [
  { key: 'overview',   label: 'Overview',   icon: BarChart2  },
  { key: 'pipeline',   label: 'Pipeline',   icon: TrendingUp },
  { key: 'customers',  label: 'Customers',  icon: Users      },
  { key: 'products',   label: 'Products',   icon: Package    },
]

// ── Helpers ────────────────────────────────────────────────────────────────────
function pct(n, d) { return d ? Math.round(n / d * 100) : 0 }
function fmt(n) {
  if (n == null) return '—'
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}
function fmtPct(v) { return v == null ? '—' : `${v.toFixed(1)}%` }
function fmtMin(m) {
  if (m == null || m === 0) return '—'
  if (m < 60) return `${m.toFixed(0)}m`
  return `${(m / 60).toFixed(1)}h`
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, label, value, sub, color = WA_GREEN, loading }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 flex flex-col gap-3 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <div className="w-8 h-8 rounded-xl flex items-center justify-center"
             style={{ background: `${color}18` }}>
          <Icon size={15} style={{ color }} />
        </div>
      </div>
      {loading
        ? <div className="h-8 w-20 bg-gray-100 rounded animate-pulse" />
        : <p className="text-2xl font-bold text-gray-900">{value}</p>}
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  )
}

function SectionCard({ title, subtitle, icon: Icon, children }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={16} className="text-gray-400" />}
        <div>
          <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
          {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
        </div>
      </div>
      {children}
    </div>
  )
}

function EmptyState({ text = 'No data yet' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-300">
      <MessageCircle size={36} className="mb-2 opacity-40" />
      <p className="text-sm">{text}</p>
    </div>
  )
}

// ── Tab: Overview ──────────────────────────────────────────────────────────────

function TabOverview({ data, loading }) {
  const labelData = data
    ? Object.entries(data.by_label || {})
        .map(([name, value]) => ({ name, value }))
        .filter(d => d.value > 0)
    : []

  const directionData = data
    ? [
        { name: 'Inbound',  value: data.total_inbound  || 0 },
        { name: 'Outbound', value: data.total_outbound || 0 },
      ].filter(d => d.value > 0)
    : []

  const dirColors = [WA_GREEN, '#3b82f6']

  return (
    <div className="space-y-4">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard icon={MessageCircle} label="Total Messages"
          value={fmt(data?.total_messages)}
          sub={`${fmt(data?.total_inbound)} inbound · ${fmt(data?.total_outbound)} outbound`}
          color={WA_GREEN} loading={loading} />
        <KpiCard icon={Zap} label="Auto-Sent Rate"
          value={fmtPct(data?.auto_sent_rate)}
          sub={`${fmt(data?.auto_sent)} of ${fmt(data?.total_sales)} sales msgs`}
          color="#f59e0b" loading={loading} />
        <KpiCard icon={Clock} label="Avg Response Time"
          value={fmtMin(data?.avg_response_time_minutes)}
          sub="Inbound Sales → replied" color="#6172f3" loading={loading} />
        <KpiCard icon={ShieldAlert} label="SLA Breaches"
          value={fmt(data?.sla_breaches)}
          sub="Sales/Support unresolved >2h" color="#ef4444" loading={loading} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Message classification pie */}
        <SectionCard title="Message Classification" subtitle="All messages by label" icon={MessageCircle}>
          {labelData.length === 0 ? <EmptyState /> : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={labelData} dataKey="value" cx="50%" cy="50%"
                       innerRadius={50} outerRadius={80} paddingAngle={2}>
                    {labelData.map(e => (
                      <Cell key={e.name} fill={LABEL_COLORS[e.name] || '#9ca3af'} />
                    ))}
                  </Pie>
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE}
                    formatter={(v, n) => [`${v} (${pct(v, data.total_messages)}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-2">
                {labelData.map(e => (
                  <div key={e.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full"
                           style={{ background: LABEL_COLORS[e.name] || '#9ca3af' }} />
                      <span className="text-xs text-gray-600">{e.name}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-semibold text-gray-800">{e.value}</span>
                      <span className="text-xs text-gray-400 ml-1">
                        ({pct(e.value, data.total_messages)}%)
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </SectionCard>

        {/* Inbound vs outbound */}
        <SectionCard title="Message Direction" subtitle="Inbound vs outbound split" icon={TrendingUp}>
          {directionData.length === 0 ? <EmptyState /> : (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={directionData} dataKey="value" cx="50%" cy="50%"
                       innerRadius={50} outerRadius={80} paddingAngle={2}>
                    {directionData.map((e, i) => (
                      <Cell key={e.name} fill={dirColors[i % dirColors.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE}
                    formatter={(v, n) => [`${v} (${pct(v, data.total_messages)}%)`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-3">
                {directionData.map((e, i) => (
                  <div key={e.name} className="p-3 rounded-xl"
                       style={{ background: `${dirColors[i]}12` }}>
                    <p className="text-xs font-semibold"
                       style={{ color: dirColors[i] }}>{e.name}</p>
                    <p className="text-xl font-bold text-gray-900">{e.value}</p>
                    <p className="text-xs text-gray-400">
                      {pct(e.value, data.total_messages)}% of total
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      {/* Volume by type */}
      <SectionCard title="Channel Performance" subtitle="Key metrics at a glance" icon={BarChart2}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Sales Messages',    value: data?.total_sales,     color: WA_GREEN  },
            { label: 'Support Messages',  value: data?.total_support,   color: '#3b82f6' },
            { label: 'Grievances',        value: data?.total_grievance, color: '#ef4444' },
            { label: 'Competitor Mentions',value: data?.competitor_mention_count, color: '#8b5cf6' },
          ].map(m => (
            <div key={m.label} className="p-3 rounded-xl bg-gray-50 text-center">
              <p className="text-xs text-gray-500 mb-1">{m.label}</p>
              <p className="text-xl font-bold" style={{ color: m.color }}>
                {fmt(loading ? null : m.value)}
              </p>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}

// ── Tab: Pipeline ──────────────────────────────────────────────────────────────

function TabPipeline({ data, loading }) {
  const statusData = data
    ? Object.entries(data.by_status || {})
        .map(([key, value]) => ({
          name:  STATUS_LABELS[key] || key,
          key,
          value,
        }))
        .filter(d => d.value > 0)
        .sort((a, b) => b.value - a.value)
    : []

  const slaTotal  = (data?.sla_breaches || 0)
  const autoTotal = data?.total_sales || 0

  return (
    <div className="space-y-4">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard icon={Zap}           label="Auto-Sent"
          value={fmt(data?.auto_sent)}
          sub={`${fmtPct(data?.auto_sent_rate)} of sales`}
          color={WA_GREEN} loading={loading} />
        <KpiCard icon={CheckCircle}   label="Draft Ready"
          value={fmt(data?.drafted_for_review)}
          sub="Awaiting human approval" color="#f59e0b" loading={loading} />
        <KpiCard icon={AlertCircle}   label="Needs Review"
          value={fmt(data?.pending_human)}
          sub="Support / Grievance" color="#ef4444" loading={loading} />
        <KpiCard icon={ShieldAlert}   label="SLA Breaches"
          value={fmt(data?.sla_breaches)}
          sub=">2h unresolved" color="#6172f3" loading={loading} />
      </div>

      {/* Status breakdown bar chart */}
      <SectionCard title="Pipeline Status Breakdown" subtitle="Messages by current status" icon={BarChart2}>
        {statusData.length === 0 ? <EmptyState /> : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={statusData} margin={{ left: 0, right: 4, bottom: 28 }} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="value" name="Messages" radius={[4, 4, 0, 0]}>
                {statusData.map(e => (
                  <Cell key={e.key} fill={STATUS_COLORS[e.key] || '#9ca3af'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </SectionCard>

      {/* Auto-send funnel */}
      <SectionCard title="AI Auto-Reply Funnel" subtitle="How WhatsApp messages flow through the AI pipeline" icon={Zap}>
        <div className="space-y-2">
          {[
            { label: 'Total Inbound',           value: data?.total_inbound,         color: WA_GREEN,  pctOf: data?.total_inbound  },
            { label: 'Classified as Sales',      value: data?.total_sales,           color: '#10b981', pctOf: data?.total_inbound  },
            { label: 'Auto-Sent by AI',          value: data?.auto_sent,             color: '#f59e0b', pctOf: data?.total_sales    },
            { label: 'Sent to Draft Review',     value: data?.drafted_for_review,    color: '#6172f3', pctOf: data?.total_sales    },
            { label: 'Flagged for Human',        value: data?.pending_human,         color: '#ef4444', pctOf: data?.total_inbound  },
          ].map(row => {
            const p = pct(row.value || 0, row.pctOf || 1)
            return (
              <div key={row.label} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-48 flex-shrink-0">{row.label}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className="h-2 rounded-full transition-all"
                       style={{ width: `${p}%`, background: row.color }} />
                </div>
                <span className="text-xs font-semibold text-gray-700 w-14 text-right">
                  {fmt(loading ? null : row.value)} ({p}%)
                </span>
              </div>
            )
          })}
        </div>
      </SectionCard>
    </div>
  )
}

// ── Tab: Knowledge ─────────────────────────────────────────────────────────────

function TabKnowledge({ data, loading }) {
  const totalGaps    = data?.knowledge_gap_count || 0
  const resRate      = data?.knowledge_gap_resolution_rate || 0
  const resolvedEst  = Math.round(totalGaps * resRate / 100)
  const unresolvedEst = totalGaps - resolvedEst

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard icon={BrainCircuit}  label="Knowledge Gaps"
          value={fmt(data?.knowledge_gap_count)}
          sub="Messages with unanswered questions"
          color="#6172f3" loading={loading} />
        <KpiCard icon={CheckCircle}   label="Gap Resolution Rate"
          value={fmtPct(data?.knowledge_gap_resolution_rate)}
          sub="% of gaps answered by team"
          color={WA_GREEN} loading={loading} />
        <KpiCard icon={MessageCircle} label="Competitor Mentions"
          value={fmt(data?.competitor_mention_count)}
          sub="Messages mentioning competitors"
          color="#ef4444" loading={loading} />
      </div>

      <SectionCard title="Knowledge Gap Status" subtitle="Resolved vs pending gaps across WhatsApp conversations" icon={BrainCircuit}>
        {totalGaps === 0 ? <EmptyState text="No knowledge gaps recorded" /> : (
          <div className="flex items-center gap-8">
            <ResponsiveContainer width="40%" height={180}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'Resolved',   value: resolvedEst   },
                    { name: 'Unresolved', value: unresolvedEst },
                  ]}
                  dataKey="value" cx="50%" cy="50%"
                  innerRadius={50} outerRadius={75} paddingAngle={3}
                >
                  <Cell fill={WA_GREEN} />
                  <Cell fill="#fee2e2" />
                </Pie>
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-4">
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100">
                <p className="text-xs font-medium text-emerald-700">Resolved Gaps</p>
                <p className="text-2xl font-bold text-emerald-800">{fmt(resolvedEst)}</p>
                <p className="text-xs text-emerald-600">
                  Answers embedded into RAG — AI now handles these automatically
                </p>
              </div>
              <div className="p-4 rounded-xl bg-red-50 border border-red-100">
                <p className="text-xs font-medium text-red-700">Unresolved Gaps</p>
                <p className="text-2xl font-bold text-red-800">{fmt(unresolvedEst)}</p>
                <p className="text-xs text-red-600">
                  Go to WhatsApp Inbox → filter "Draft Ready" to fill these in
                </p>
              </div>
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Why Knowledge Gaps Matter" icon={BrainCircuit}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { icon: Zap,           color: WA_GREEN,  title: 'Fills automatically',
              text: 'Every answer you provide is embedded into the RAG pipeline so the next customer gets a complete auto-reply.' },
            { icon: TrendingUp,    color: '#6172f3', title: 'Improves over time',
              text: `Your AI has answered ${fmtPct(resRate)} of questions raised. Every resolved gap raises this rate.` },
            { icon: ShieldAlert,   color: '#f59e0b', title: 'Reduces SLA breaches',
              text: 'Knowledge gaps are the primary cause of draft-review bottlenecks. Filling them enables full automation.' },
          ].map(c => (
            <div key={c.title} className="p-4 rounded-xl bg-gray-50">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-2"
                   style={{ background: `${c.color}18` }}>
                <c.icon size={15} style={{ color: c.color }} />
              </div>
              <p className="text-xs font-semibold text-gray-800 mb-1">{c.title}</p>
              <p className="text-xs text-gray-500">{c.text}</p>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}

// ── Tab: Customers ─────────────────────────────────────────────────────────────

function TabCustomers({ data, loading }) {
  const [selectedPhone, setSelectedPhone] = useState(null)
  const senders = data?.top_senders || []

  const { data: convData, isLoading: convLoading } = useQuery({
    queryKey: ['wa-conversation', selectedPhone],
    queryFn: () => new Promise((res, rej) =>
      GetWhatsAppConversationService(selectedPhone, { limit: 30 }, res, (_, e) => rej(e))
    ),
    enabled: !!selectedPhone,
  })

  const LABEL_BADGE = {
    Sales: 'bg-emerald-100 text-emerald-700', Support: 'bg-blue-100 text-blue-700',
    Grievance: 'bg-red-100 text-red-700', Unclassified: 'bg-gray-100 text-gray-500',
  }

  return (
    <div className="flex gap-4 h-full">
      {/* Left: sender list */}
      <div className="w-80 flex-shrink-0 space-y-3">
        <h3 className="text-sm font-semibold text-gray-800">
          Top Customers <span className="text-xs font-normal text-gray-400 ml-1">by message volume</span>
        </h3>
        {loading && <p className="text-xs text-gray-400">Loading…</p>}
        {!loading && senders.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <Users size={32} className="mx-auto mb-2 opacity-20" />
            <p className="text-sm">No inbound messages yet</p>
          </div>
        )}
        {senders.map((s, i) => (
          <button
            key={s.from_number}
            onClick={() => setSelectedPhone(s.from_number)}
            className={`w-full text-left p-3 rounded-xl border transition-all
              ${selectedPhone === s.from_number
                ? 'border-[#25D366] bg-emerald-50'
                : 'border-gray-100 bg-white hover:border-gray-200'}`}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-[#25D366] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                {(s.from_number || '??').slice(-2)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-gray-900 truncate">{s.from_number}</p>
                {s.lead_name && <p className="text-xs text-gray-500 truncate">{s.lead_name}</p>}
                <div className="flex items-center gap-1 mt-1 flex-wrap">
                  {Object.entries(s.labels || {}).slice(0, 2).map(([lbl, n]) => (
                    <span key={lbl} className={`text-xs px-1.5 py-0.5 rounded-full ${LABEL_BADGE[lbl] || 'bg-gray-100 text-gray-500'}`}>
                      {lbl}: {n}
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-sm font-bold text-gray-900">{s.total}</p>
                <p className="text-xs text-gray-400">msgs</p>
              </div>
            </div>
            {s.last_at && (
              <p className="text-xs text-gray-400 mt-1.5 pl-12">
                Last: {new Date(s.last_at).toLocaleDateString()}
              </p>
            )}
          </button>
        ))}
      </div>

      {/* Right: conversation history */}
      <div className="flex-1 min-w-0">
        {!selectedPhone ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-300">
            <MessageCircle size={40} className="mb-3 opacity-30" />
            <p className="text-sm">Select a customer to view conversation history</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-[#25D366] flex items-center justify-center text-white text-xs font-bold">
                {(selectedPhone || '??').slice(-2)}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">{selectedPhone}</h3>
                <p className="text-xs text-gray-400">
                  {convData?.total || 0} messages · Conversation history
                </p>
              </div>
            </div>

            {convLoading && <p className="text-xs text-gray-400 p-4">Loading…</p>}
            {!convLoading && (convData?.items || []).length === 0 && (
              <p className="text-xs text-gray-400 p-4">No messages found</p>
            )}
            <div className="space-y-2 max-h-[60vh] overflow-y-auto">
              {(convData?.items || []).map(m => {
                const isInbound = m.direction === 'inbound'
                return (
                  <div key={m.id} className={`flex ${isInbound ? 'justify-start' : 'justify-end'}`}>
                    <div className={`max-w-sm rounded-xl p-3 text-xs
                      ${isInbound ? 'bg-white border border-gray-200' : 'bg-[#25D366] text-white'}`}>
                      <p className={`leading-relaxed ${isInbound ? 'text-gray-800' : 'text-white'}`}>
                        {m.body || '(no text)'}
                      </p>
                      <div className={`flex items-center gap-2 mt-1.5 ${isInbound ? 'text-gray-400' : 'text-white/70'}`}>
                        <span>{new Date(m.received_at).toLocaleString()}</span>
                        {m.detected_product_name && (
                          <span className={`px-1.5 py-0.5 rounded text-xs
                            ${isInbound ? 'bg-emerald-100 text-emerald-700' : 'bg-white/20 text-white'}`}>
                            {m.detected_product_name}
                          </span>
                        )}
                        {m.label && m.label !== 'Unclassified' && (
                          <span className={isInbound ? 'text-gray-400' : 'text-white/60'}>{m.label}</span>
                        )}
                      </div>
                      {m.ai_draft && isInbound && (
                        <div className="mt-2 p-2 bg-amber-50 rounded border border-amber-100">
                          <p className="text-amber-700 text-xs font-medium mb-0.5">AI Draft</p>
                          <p className="text-gray-700 text-xs">{m.ai_draft.slice(0, 120)}{m.ai_draft.length > 120 ? '…' : ''}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab: Products ──────────────────────────────────────────────────────────────

function TabProducts({ data, loading }) {
  const products = data?.top_products || []

  return (
    <div className="space-y-4">
      <SectionCard title="Most Inquired Products" subtitle="Products detected across WhatsApp messages" icon={Package}>
        {loading && <p className="text-xs text-gray-400">Loading…</p>}
        {!loading && products.length === 0 && (
          <EmptyState text="No product mentions detected yet" />
        )}
        {!loading && products.length > 0 && (
          <div className="space-y-2">
            {products.map((p, i) => {
              const pct = p.inquiries ? Math.round(p.converted / p.inquiries * 100) : 0
              return (
                <div key={p.name} className="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
                    ${i === 0 ? 'bg-amber-100 text-amber-700' : i === 1 ? 'bg-gray-200 text-gray-600' : i === 2 ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-400'}`}>
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-gray-900 truncate">{p.name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                        <div className="h-1.5 rounded-full bg-[#25D366]"
                             style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0">{pct}% converted</span>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-bold text-gray-900">{p.inquiries}</p>
                    <p className="text-xs text-gray-400">inquiries</p>
                  </div>
                  <div className="text-right flex-shrink-0 w-16">
                    <p className="text-sm font-bold text-emerald-600">{p.converted}</p>
                    <p className="text-xs text-gray-400">replied</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </SectionCard>

      {/* Products bar chart */}
      {products.length > 0 && (
        <SectionCard title="Inquiries vs Replies by Product" icon={BarChart2}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart
              data={products.slice(0, 10).map(p => ({ name: p.name.slice(0, 20), inquiries: p.inquiries, replied: p.converted }))}
              margin={{ left: 0, right: 4, bottom: 50 }} barGap={2}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="inquiries" name="Total Inquiries" fill="#d1fae5" radius={[3, 3, 0, 0]} />
              <Bar dataKey="replied"   name="Replied"         fill={WA_GREEN}  radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function WhatsAppAnalytics() {
  const [activeTab, setActiveTab] = useState('overview')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['wa-analytics-full'],
    queryFn: () => new Promise((res, rej) =>
      GetWhatsAppAnalyticsService(res, (_, e) => rej(e))
    ),
    staleTime: 60_000,
  })

  return (
    <div className="flex flex-col min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center"
               style={{ background: WA_GREEN }}>
            <MessageCircle size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-gray-900">WhatsApp Analytics</h1>
            <p className="text-xs text-gray-400">Meta Cloud API — message intelligence & pipeline metrics</p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="flex gap-1">
          {TABS.map(t => {
            const Icon = t.icon
            return (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-3 text-xs font-medium border-b-2 transition-colors
                  ${activeTab === t.key
                    ? 'border-[#25D366] text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700'}`}
              >
                <Icon size={13} />
                {t.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-5xl mx-auto">
          {isLoading && !data ? (
            <div className="flex items-center justify-center h-64 text-gray-400">
              <RefreshCw size={24} className="animate-spin mr-3" />
              <span className="text-sm">Loading WhatsApp analytics…</span>
            </div>
          ) : !data ? (
            <div className="flex flex-col items-center justify-center h-64 text-gray-400">
              <MessageCircle size={40} className="mb-3 opacity-20" />
              <p className="text-sm">No WhatsApp data yet</p>
              <p className="text-xs mt-1">Connect a WhatsApp Business account and start receiving messages</p>
            </div>
          ) : (
            <>
              {activeTab === 'overview'  && <TabOverview  data={data} loading={isLoading} />}
              {activeTab === 'pipeline'  && <TabPipeline  data={data} loading={isLoading} />}
              {activeTab === 'customers' && <TabCustomers data={data} loading={isLoading} />}
              {activeTab === 'products'  && <TabProducts  data={data} loading={isLoading} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

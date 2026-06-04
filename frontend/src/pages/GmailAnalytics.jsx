import { useState, useEffect, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail, Clock, Zap, RefreshCw, ArrowDown, ArrowUp, ShieldAlert,
  CheckCircle, AlertCircle, TrendingUp, Package, DollarSign,
  ShoppingCart, Users, Building2, BarChart2, Activity, Target,
  Inbox, Filter, ChevronRight, Search, Shield
} from 'lucide-react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip as RechartsTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  LineChart, Line, AreaChart, Area
} from 'recharts'
import { GetGmailAnalyticsService, GetEmailAccountsService, BackfillProductsService } from '../services/ApiService'
import ApplicationStore from '../utils/ApplicationStore'

// ─── Constants ────────────────────────────────────────────────────────────────

const LABEL_COLORS = {
  Sales: '#6172f3', Support: '#3b82f6', Grievance: '#ef4444',
  Transactional: '#9ca3af', Promotional: '#8b5cf6', Personal: '#ec4899', Unclassified: '#6b7280',
}
const STATUS_COLORS = {
  new: '#3b82f6', classified: '#9ca3af', draft_ready: '#f59e0b',
  pending_human: '#ef4444', replied: '#10b981', archived: '#6b7280', ignored: '#d1d5db',
}
const STATUS_LABELS = {
  new: 'New', classified: 'Classified', draft_ready: 'Draft Ready',
  pending_human: 'Needs Review', replied: 'Replied', archived: 'Archived', ignored: 'Ignored',
}
const SRC_COLORS = ['#6172f3','#10b981','#f59e0b','#ef4444','#8b5cf6','#3b82f6','#ec4899','#14b8a6','#f97316','#64748b']
const TIME_RANGES = [
  { key: '7h', label: '7h' }, { key: '24h', label: '24h' },
  { key: '48h', label: '48h' }, { key: '7d', label: '7 days' }, { key: 'all', label: 'All' },
]
const TABS = [
  { key: 'overview',   label: 'Overview',   icon: BarChart2 },
  { key: 'pipeline',   label: 'Pipeline',   icon: Activity },
  { key: 'products',   label: 'Products',   icon: Package },
  { key: 'resolution', label: 'Resolution', icon: CheckCircle },
]
const TOOLTIP_STYLE = { borderRadius: 10, border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.10)', fontSize: 12 }

function fmt(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString()
}

// ─── Reusable components ──────────────────────────────────────────────────────

function KpiCard({ icon: Icon, label, value, sub, color, loading, trend }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-2xl bg-white border border-gray-100 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="absolute top-0 right-0 w-24 h-24 rounded-full -translate-y-8 translate-x-8 opacity-[0.06]"
        style={{ background: color }} />
      <div className="flex items-start justify-between">
        <div className="p-2 rounded-xl" style={{ background: `${color}15` }}>
          <Icon size={18} style={{ color }} />
        </div>
        {trend !== undefined && (
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${trend >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'}`}>
            {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="mt-3">
        {loading
          ? <div className="h-7 w-20 bg-gray-100 rounded-lg animate-pulse mb-1" />
          : <p className="text-2xl font-black text-gray-900">{value}</p>}
        <p className="text-xs font-semibold text-gray-500 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </motion.div>
  )
}

function SectionCard({ title, subtitle, icon: Icon, iconColor = '#6172f3', children, action }) {
  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-50">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg" style={{ background: `${iconColor}15` }}>
            <Icon size={15} style={{ color: iconColor }} />
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900">{title}</p>
            {subtitle && <p className="text-[11px] text-gray-400">{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}

function EmptyState({ text = 'No data yet' }) {
  return (
    <div className="h-40 flex flex-col items-center justify-center gap-2 text-gray-300">
      <BarChart2 size={28} />
      <p className="text-xs font-medium text-gray-400">{text}</p>
    </div>
  )
}

function ResolutionBar({ label, total, resolved, pending, color }) {
  const pct = total ? Math.round(resolved / total * 100) : 0
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-gray-700">{label}</span>
        <span className="text-gray-400">{resolved}/{total} resolved · <span className="font-bold" style={{ color }}>{pct}%</span></span>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <motion.div className="h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }} style={{ background: color }} />
      </div>
      <div className="flex gap-4 text-[11px]">
        <span className="flex items-center gap-1 text-emerald-500"><CheckCircle size={10} /> {resolved} resolved</span>
        <span className="flex items-center gap-1 text-red-400"><AlertCircle size={10} /> {pending} pending</span>
      </div>
    </div>
  )
}

// ─── Tab: Overview ────────────────────────────────────────────────────────────

function TabOverview({ data, loading }) {
  const vb = data?.total_volume_breakdown || {}
  const tiles = [
    { label: 'Total',     value: vb.Total     ?? data?.total_emails,       color: '#6172f3' },
    { label: 'Inbound',   value: vb.Inbound   ?? data?.total_inbound,      color: '#3b82f6' },
    { label: 'Outbound',  value: vb.Outbound  ?? data?.total_outbound,     color: '#10b981' },
    { label: 'Sales',     value: vb.Sales     ?? data?.total_sales_emails, color: '#8b5cf6' },
    { label: 'Support',   value: vb.Support   ?? data?.support_total,      color: '#3b82f6' },
    { label: 'Grievance', value: vb.Grievance ?? data?.grievance_total,    color: '#ef4444' },
    { label: 'Replied',   value: vb.Replied,                               color: '#10b981' },
    { label: 'Pending',   value: vb.Pending   ?? data?.pending_human,      color: '#f59e0b' },
  ]

  const labelData = data ? Object.entries(data.by_label || {}).map(([name, value]) => ({ name, value })).filter(d => d.value > 0) : []
  const dailyData = data?.daily_stats || []

  return (
    <div className="space-y-6">
      {/* Volume tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        {tiles.map(({ label, value, color }) => (
          <div key={label} className="rounded-xl bg-white border border-gray-100 p-3 text-center shadow-sm hover:shadow transition-shadow">
            {loading
              ? <div className="h-6 w-12 mx-auto bg-gray-100 rounded animate-pulse mb-1" />
              : <p className="text-xl font-black" style={{ color }}>{fmt(value ?? 0)}</p>}
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily volume */}
        <div className="lg:col-span-2">
          <SectionCard title="Email Volume" subtitle="Inbound vs outbound over time" icon={BarChart2}>
            {loading ? <EmptyState text="Loading…" /> : dailyData.length === 0 ? <EmptyState /> : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={dailyData} margin={{ left: 0, right: 4 }}>
                  <defs>
                    <linearGradient id="inboundGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6172f3" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#6172f3" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="outboundGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Area type="monotone" dataKey="inbound" name="Inbound" stroke="#6172f3" strokeWidth={2} fill="url(#inboundGrad)" dot={false} />
                  <Area type="monotone" dataKey="outbound" name="Outbound" stroke="#10b981" strokeWidth={2} fill="url(#outboundGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </SectionCard>
        </div>

        {/* Classification */}
        <SectionCard title="By Label" subtitle="Email classification breakdown" icon={Filter} iconColor="#8b5cf6">
          {loading ? <EmptyState text="Loading…" /> : labelData.length === 0 ? <EmptyState /> : (
            <div className="space-y-3">
              <ResponsiveContainer width="100%" height={140}>
                <PieChart>
                  <Pie data={labelData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={2} dataKey="value">
                    {labelData.map(e => <Cell key={e.name} fill={LABEL_COLORS[e.name] || '#9ca3af'} />)}
                  </Pie>
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5">
                {labelData.sort((a, b) => b.value - a.value).map(({ name, value }) => {
                  const total = labelData.reduce((s, d) => s + d.value, 0)
                  const pct = total ? Math.round(value / total * 100) : 0
                  const color = LABEL_COLORS[name] || '#9ca3af'
                  return (
                    <div key={name} className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-[11px] text-gray-600 flex-1">{name}</span>
                      <div className="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                      </div>
                      <span className="text-[11px] font-bold text-gray-700 w-5 text-right">{value}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      {/* Performance KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={Zap}         label="Auto-Sent Rate"    value={loading ? '—' : `${data?.auto_sent_rate_pct ?? 0}%`}         color="#10b981" loading={loading} sub="No human touch needed" />
        <KpiCard icon={Clock}       label="Avg Reply Time"    value={loading ? '—' : `${data?.avg_reply_minutes ?? 0}m`}           color="#f59e0b" loading={loading} sub="Sales emails only" />
        <KpiCard icon={ShieldAlert} label="SLA Compliance"    value={loading ? '—' : (() => { const t=(data?.sla_met??0)+(data?.sla_breached??0); return t ? `${Math.round((data?.sla_met??0)/t*100)}%` : '—' })()} color="#6172f3" loading={loading} sub={`${data?.sla_met??0} met · ${data?.sla_breached??0} breached`} />
        <KpiCard icon={TrendingUp}  label="Conversion Rate"   value={loading ? '—' : `${data?.conversion_rate_pct ?? 0}%`}        color="#8b5cf6" loading={loading} sub="Sales → replied" />
      </div>
    </div>
  )
}

// ─── Tab: Pipeline ────────────────────────────────────────────────────────────

function TabPipeline({ data, loading }) {
  const statusData = data ? Object.entries(data.by_status || {}).map(([key, value]) => ({ name: STATUS_LABELS[key] || key, key, value })).filter(d => d.value > 0) : []
  const dailyData = data?.daily_stats || []
  const slaTotal = (data?.sla_met ?? 0) + (data?.sla_breached ?? 0)
  const slaMetPct = slaTotal ? Math.round((data?.sla_met ?? 0) / slaTotal * 100) : 0
  const slaColor = slaMetPct >= 80 ? '#10b981' : slaMetPct >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div className="space-y-6">
      {/* Sales pipeline metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: Zap,         label: 'Auto-Sent',         value: data?.auto_sent,          color: '#10b981', sub: 'No human needed' },
          { icon: Clock,       label: 'Drafted for Review', value: data?.drafted_for_review, color: '#f59e0b', sub: 'Had knowledge gaps' },
          { icon: AlertCircle, label: 'Pending Human',      value: data?.pending_human,       color: '#ef4444', sub: 'Support / Grievance' },
          { icon: ShieldAlert, label: 'SLA Breaches',       value: data?.sla_breached,        color: slaColor,  sub: '>2h without reply' },
        ].map(({ icon, label, value, color, sub }) => (
          <KpiCard key={label} icon={icon} label={label} value={fmt(value)} color={color} loading={loading} sub={sub} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SLA trend */}
        <SectionCard title="SLA Performance" subtitle="Sales emails answered within 2h" icon={ShieldAlert} iconColor={slaColor}>
          {loading ? <EmptyState text="Loading…" /> : (
            <div className="space-y-4">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={dailyData} margin={{ left: 0, right: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="sla_met"      name="SLA Met"     stroke="#10b981" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="sla_breached" name="SLA Breached" stroke="#ef4444" strokeWidth={2} dot={false} strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-500">{slaTotal} emails tracked</span>
                  <span className="font-bold" style={{ color: slaColor }}>{slaMetPct}% within 2h</span>
                </div>
                <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                  <motion.div className="h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${slaMetPct}%` }}
                    transition={{ duration: 0.8 }} style={{ background: slaColor }} />
                </div>
              </div>
            </div>
          )}
        </SectionCard>

        {/* Status bar */}
        <SectionCard title="Pipeline Status" subtitle="Email status distribution" icon={Activity} iconColor="#6172f3">
          {loading ? <EmptyState text="Loading…" /> : statusData.length === 0 ? <EmptyState /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={statusData} margin={{ left: 0, right: 4, bottom: 28 }} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#9ca3af' }} axisLine={false} tickLine={false} interval={0} angle={-35} textAnchor="end" />
                <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} axisLine={false} tickLine={false} allowDecimals={false} width={24} />
                <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="value" name="Count" radius={[5, 5, 0, 0]} maxBarSize={32}>
                  {statusData.map(e => <Cell key={e.key} fill={STATUS_COLORS[e.key] || '#9ca3af'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      </div>

      {/* Account breakdown */}
      {data?.by_account && Object.keys(data.by_account).length > 0 && (
        <SectionCard title="Volume by Account" subtitle="Emails per connected Gmail account" icon={Inbox} iconColor="#3b82f6">
          <div className="space-y-3">
            {Object.entries(data.by_account).sort(([,a],[,b]) => b-a).map(([email, count], i) => {
              const total = Object.values(data.by_account).reduce((s, v) => s + v, 0)
              const pct = total ? Math.round(count / total * 100) : 0
              const color = SRC_COLORS[i % SRC_COLORS.length]
              return (
                <div key={email} className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-xs text-gray-600 flex-1 truncate">{email}</span>
                  <div className="w-32 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <span className="text-xs font-bold text-gray-700 w-8 text-right">{count}</span>
                  <span className="text-[10px] text-gray-400 w-8 text-right">{pct}%</span>
                </div>
              )
            })}
          </div>
        </SectionCard>
      )}

      {/* Owner breakdown — super-admin only */}
      {(() => {
        const { userDetails } = ApplicationStore().getStorage('userDetails') || {}
        const isSuperAdmin = userDetails?.userRole === 'Admin'
        if (!isSuperAdmin || !data?.by_owner || Object.keys(data.by_owner).length === 0) return null
        return (
          <SectionCard title="Volume by Team Member" subtitle="Which user's Gmail account received each email" icon={Shield} iconColor="#7c3aed">
            <div className="space-y-4">
              {Object.entries(data.by_owner).sort(([,a],[,b]) => b.email_count - a.email_count).map(([userEmail, info], i) => {
                const total = Object.values(data.by_owner).reduce((s, v) => s + v.email_count, 0)
                const pct = total ? Math.round(info.email_count / total * 100) : 0
                const color = SRC_COLORS[i % SRC_COLORS.length]
                return (
                  <div key={userEmail} className="space-y-1.5">
                    <div className="flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                      <span className="text-xs font-semibold text-gray-800 flex-1 truncate">{userEmail}</span>
                      <span className="text-xs font-bold text-gray-700 w-8 text-right">{info.email_count}</span>
                      <span className="text-[10px] text-gray-400 w-8 text-right">{pct}%</span>
                    </div>
                    <div className="ml-5 flex flex-wrap gap-1.5">
                      {(info.gmail_accounts || []).map(gmail => (
                        <span key={gmail} className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-100">
                          <Mail size={8} /> {gmail}
                        </span>
                      ))}
                    </div>
                    <div className="ml-5 h-1 rounded-full bg-gray-100 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </SectionCard>
        )
      })()}
    </div>
  )
}

// ─── Tab: Products ────────────────────────────────────────────────────────────

function ProductIntelligence({ data, loading }) {
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [srcFilter, setSrcFilter] = useState('All')
  const noData = !data?.by_product || Object.keys(data.by_product).length === 0

  const allProducts = useMemo(() => {
    if (!data?.top_products_purchased) return []
    return data.top_products_purchased.filter(p =>
      !search || p.name.toLowerCase().includes(search.toLowerCase())
    )
  }, [data, search])

  const sourceGroups = useMemo(() => {
    if (!data?.product_source_rows) return []
    const rows = srcFilter === 'All' ? data.product_source_rows : data.product_source_rows.filter(r => r.source === srcFilter)
    const map = {}
    rows.forEach(r => { if (!map[r.source]) map[r.source] = []; map[r.source].push(r) })
    return Object.entries(map).map(([src, items]) => ({ src, items: items.sort((a, b) => b.count - a.count).slice(0, 8), total: items.reduce((s, i) => s + i.count, 0) })).sort((a, b) => b.total - a.total)
  }, [data, srcFilter])

  const allSources = useMemo(() => data?.product_source_rows ? ['All', ...new Set(data.product_source_rows.map(r => r.source))] : [], [data])

  const companyRows = useMemo(() => {
    if (!data?.product_company_rows) return []
    return data.product_company_rows.filter(c =>
      !search || c.company.toLowerCase().includes(search.toLowerCase()) ||
      c.email.toLowerCase().includes(search.toLowerCase()) ||
      c.products.some(p => p.name.toLowerCase().includes(search.toLowerCase()))
    )
  }, [data, search])

  const INNER_TABS = [{ key: 'all', label: 'All Products' }, { key: 'source', label: 'By Source' }, { key: 'company', label: 'By Company' }]

  return (
    <SectionCard title="Product Intelligence" subtitle="Inquiries tracked across emails, sources & companies" icon={Package} iconColor="#6172f3"
      action={
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search…"
              className="text-xs pl-7 pr-3 py-1.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:border-indigo-400 w-36" />
          </div>
          <div className="flex bg-gray-100 rounded-lg overflow-hidden">
            {INNER_TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`px-3 py-1.5 text-[11px] font-semibold transition-all ${tab === t.key ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:text-gray-700'}`}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
      }>
      {loading ? <EmptyState text="Loading…" /> : noData ? (
        <div className="h-40 flex flex-col items-center justify-center gap-2 text-gray-300">
          <Package size={28} />
          <p className="text-xs text-gray-400">No product data yet — click <strong className="text-indigo-500">Detect Products</strong> to backfill</p>
        </div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>

            {tab === 'all' && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="border-b border-gray-100">
                    {['#','Product','Inquiries','Converted','Rate',''].map(h => <th key={h} className={`text-[10px] font-semibold text-gray-400 uppercase tracking-wide pb-2 ${h === 'Product' ? 'text-left' : 'text-right'}`}>{h}</th>)}
                  </tr></thead>
                  <tbody className="divide-y divide-gray-50">
                    {allProducts.length === 0
                      ? <tr><td colSpan={6} className="py-6 text-center text-gray-400 text-xs">No results</td></tr>
                      : allProducts.map(({ name, inquiries, converted, conversion_pct }, i) => (
                        <tr key={name} className="hover:bg-indigo-50/30 transition-colors group">
                          <td className="py-2 pr-2 text-right text-gray-300 font-bold w-6">{i + 1}</td>
                          <td className="py-2 pr-3"><span className="font-semibold text-gray-800 group-hover:text-indigo-700 transition-colors">{name}</span></td>
                          <td className="text-right font-bold text-indigo-600 py-2 w-16">{inquiries}</td>
                          <td className="text-right font-bold text-emerald-600 py-2 w-16">{converted}</td>
                          <td className="text-right py-2 w-14">
                            <span className={`text-[10px] font-black px-1.5 py-0.5 rounded-full ${conversion_pct >= 50 ? 'bg-emerald-100 text-emerald-700' : conversion_pct > 0 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-400'}`}>
                              {conversion_pct}%
                            </span>
                          </td>
                          <td className="py-2 pl-2 w-24">
                            <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                              <div className="h-full rounded-full bg-indigo-400" style={{ width: `${Math.round(inquiries / (allProducts[0]?.inquiries || 1) * 100)}%` }} />
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}

            {tab === 'source' && (
              <div className="space-y-4">
                <div className="flex gap-1.5 flex-wrap">
                  {allSources.map((s, i) => (
                    <button key={s} onClick={() => setSrcFilter(s)}
                      className={`text-[10px] font-bold px-2.5 py-1 rounded-full border transition-all ${srcFilter === s ? 'text-white border-transparent' : 'bg-white text-gray-500 border-gray-200 hover:border-indigo-300'}`}
                      style={srcFilter === s ? { background: SRC_COLORS[(i) % SRC_COLORS.length] } : {}}>
                      {s}
                    </button>
                  ))}
                </div>
                {sourceGroups.length === 0 ? <EmptyState text="No data for this source" /> : sourceGroups.map(({ src, items, total }, gi) => {
                  const color = SRC_COLORS[gi % SRC_COLORS.length]
                  const maxC = items[0]?.count || 1
                  return (
                    <div key={src} className="rounded-xl border border-gray-100 overflow-hidden">
                      <div className="flex items-center justify-between px-4 py-2.5" style={{ background: `${color}10` }}>
                        <div className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                          <span className="text-xs font-bold text-gray-800">{src}</span>
                        </div>
                        <span className="text-[10px] font-semibold text-gray-400">{total} inquiries</span>
                      </div>
                      <div className="px-4 py-3 space-y-2">
                        {items.map(({ product, count, converted }) => (
                          <div key={product} className="flex items-center gap-3">
                            <span className="text-xs text-gray-700 flex-1 truncate">{product}</span>
                            <div className="w-28 h-1.5 rounded-full bg-gray-100 overflow-hidden flex-shrink-0">
                              <div className="h-full rounded-full" style={{ width: `${Math.round(count / maxC * 100)}%`, background: color }} />
                            </div>
                            <span className="text-xs font-bold text-gray-700 w-4 text-right">{count}</span>
                            {converted > 0 && <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded-full">✓{converted}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {tab === 'company' && (
              <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
                {companyRows.length === 0 ? <EmptyState text="No results" /> : companyRows.map((row, i) => {
                  const color = SRC_COLORS[i % SRC_COLORS.length]
                  return (
                    <div key={row.email} className="rounded-xl border border-gray-100 p-3 hover:border-indigo-100 hover:bg-indigo-50/20 transition-all">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center text-white text-xs font-black" style={{ background: color }}>
                            {row.company[0]?.toUpperCase() || '?'}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-gray-900 truncate">{row.company}</p>
                            <p className="text-[10px] text-gray-400 truncate">{row.email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white" style={{ background: color }}>{row.source}</span>
                          <span className="text-[10px] font-semibold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{row.total_emails} emails</span>
                        </div>
                      </div>
                      {row.products.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                          {row.products.map(({ name, count }) => (
                            <span key={name} className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-700 flex items-center gap-1">
                              <span className="truncate max-w-[140px]">{name}</span>
                              <span className="font-black text-indigo-500">×{count}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      )}
    </SectionCard>
  )
}

function TabProducts({ data, loading }) {
  return (
    <div className="space-y-6">
      {/* Revenue KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={DollarSign}   label="Total Revenue"     value={loading ? '—' : `₹${Number(data?.revenue_total ?? 0).toLocaleString()}`} color="#10b981" loading={loading} sub="From orders & invoices" />
        <KpiCard icon={ShoppingCart} label="Orders / Invoices" value={fmt(data?.order_count)}  color="#3b82f6" loading={loading} sub="Confirmed orders received" />
        <KpiCard icon={Package}      label="POs Raised"        value={fmt(data?.po_count)}     color="#8b5cf6" loading={loading} sub="Purchase orders in emails" />
        <KpiCard icon={TrendingUp}   label="Conversion Rate"   value={loading ? '—' : `${data?.conversion_rate_pct ?? 0}%`} color="#f59e0b" loading={loading} sub="Sales → replied" />
      </div>

      <ProductIntelligence data={data} loading={loading} />
    </div>
  )
}

// ─── Tab: Resolution ──────────────────────────────────────────────────────────

function TabResolution({ data, loading }) {
  const PIPELINE_COLORS = { Hot: '#ef4444', Warm: '#f59e0b', Cold: '#3b82f6', Unknown: '#9ca3af' }
  const ORDER = ['Hot', 'Warm', 'Cold', 'Unknown']
  const pipelineData = ORDER.filter(k => data?.lead_pipeline?.[k]).map(k => ({ name: k, value: data.lead_pipeline[k], color: PIPELINE_COLORS[k] }))
  const total = pipelineData.reduce((s, d) => s + d.value, 0)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={AlertCircle} label="Grievance Pending"  value={fmt(data?.grievance_pending)}  color="#ef4444" loading={loading} />
        <KpiCard icon={CheckCircle} label="Grievance Resolved" value={fmt(data?.grievance_resolved)} color="#10b981" loading={loading} />
        <KpiCard icon={AlertCircle} label="Support Pending"    value={fmt(data?.support_pending)}    color="#f59e0b" loading={loading} />
        <KpiCard icon={CheckCircle} label="Support Resolved"   value={fmt(data?.support_resolved)}   color="#3b82f6" loading={loading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resolution bars */}
        <SectionCard title="Support & Grievance" subtitle="Resolution progress" icon={CheckCircle} iconColor="#10b981">
          {loading ? <EmptyState text="Loading…" /> : (
            <div className="space-y-6">
              <ResolutionBar label="Grievance" total={data?.grievance_total ?? 0} resolved={data?.grievance_resolved ?? 0} pending={data?.grievance_pending ?? 0} color="#ef4444" />
              <ResolutionBar label="Support"   total={data?.support_total ?? 0}   resolved={data?.support_resolved ?? 0}   pending={data?.support_pending ?? 0}   color="#3b82f6" />
            </div>
          )}
        </SectionCard>

        {/* Lead pipeline */}
        <SectionCard title="Lead Interest Pipeline" subtitle="Interest levels of leads who emailed" icon={Users} iconColor="#8b5cf6">
          {loading ? <EmptyState text="Loading…" /> : pipelineData.length === 0 ? <EmptyState text="No lead data yet" /> : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={150} height={150}>
                <PieChart>
                  <Pie data={pipelineData} cx="50%" cy="50%" innerRadius={38} outerRadius={68} paddingAngle={3} dataKey="value">
                    {pipelineData.map(({ name, color }) => <Cell key={name} fill={color} />)}
                  </Pie>
                  <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-3">
                {pipelineData.map(({ name, value, color }) => (
                  <div key={name} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                    <span className="text-xs text-gray-600 flex-1">{name}</span>
                    <span className="text-sm font-black" style={{ color }}>{value}</span>
                    <span className="text-[10px] text-gray-400">{total ? Math.round(value / total * 100) : 0}%</span>
                  </div>
                ))}
                <div className="pt-2 border-t border-gray-100 flex items-center gap-2">
                  <Users size={11} className="text-gray-400" />
                  <span className="text-[11px] text-gray-400">{total} unique leads</span>
                </div>
              </div>
            </div>
          )}
        </SectionCard>
      </div>

      {/* Source segmentation */}
      {data?.by_company_source && Object.keys(data.by_company_source).length > 0 && (
        <SectionCard title="Email Source Segmentation" subtitle="Where inbound sales inquiries are coming from" icon={Building2} iconColor="#6172f3">
          {(() => {
            const srcData = Object.entries(data.by_company_source).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count)
            const total = srcData.reduce((s, d) => s + d.count, 0)
            return (
              <div className="flex gap-6 items-center">
                <div className="flex-shrink-0">
                  <ResponsiveContainer width={150} height={150}>
                    <PieChart>
                      <Pie data={srcData.slice(0,8)} dataKey="count" cx="50%" cy="50%" innerRadius={35} outerRadius={68} paddingAngle={2}>
                        {srcData.slice(0,8).map((_, i) => <Cell key={i} fill={SRC_COLORS[i % SRC_COLORS.length]} />)}
                      </Pie>
                      <RechartsTooltip contentStyle={TOOLTIP_STYLE} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 space-y-2">
                  {srcData.map(({ name, count }, i) => {
                    const pct = Math.round(count / total * 100)
                    const color = SRC_COLORS[i % SRC_COLORS.length]
                    return (
                      <div key={name} className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                        <span className="text-xs text-gray-700 flex-1 truncate">{name}</span>
                        <div className="w-20 h-1.5 rounded-full bg-gray-100 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                        </div>
                        <span className="text-xs font-bold text-gray-700 w-5 text-right">{count}</span>
                        <span className="text-[10px] text-gray-400 w-8 text-right">{pct}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })()}
        </SectionCard>
      )}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function GmailAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [since, setSince] = useState('7d')
  const [accounts, setAccounts] = useState([])
  const [activeAccount, setActiveAccount] = useState('')
  const [activeTab, setActiveTab] = useState('overview')
  const [backfilling, setBackfilling] = useState(false)
  const [backfillResult, setBackfillResult] = useState(null)
  const tabBarRef = useRef(null)

  useEffect(() => {
    GetEmailAccountsService(res => setAccounts(res?.items || []), () => {})
  }, [])

  const load = (s = since, acc = activeAccount) => {
    setLoading(true)
    GetGmailAnalyticsService(s, acc || null, res => { setData(res); setLoading(false) }, () => setLoading(false))
  }

  useEffect(() => { load(since, activeAccount) }, [since, activeAccount])

  const handleBackfill = () => {
    setBackfilling(true)
    setBackfillResult(null)
    BackfillProductsService(
      res => { setBackfilling(false); setBackfillResult(res); load(since, activeAccount) },
      () => { setBackfilling(false); setBackfillResult({ error: true }) }
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Page header */}
      <div className="bg-white border-b border-gray-100 px-6 py-5">
        <div className="max-w-[1400px] mx-auto">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-xl font-black text-gray-900 tracking-tight">Email Analytics</h1>
              <p className="text-xs text-gray-400 mt-0.5">Pipeline performance, product intelligence & resolution tracking</p>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2 flex-wrap">
              {accounts.length > 1 && (
                <select value={activeAccount} onChange={e => setActiveAccount(e.target.value)}
                  className="text-xs border border-gray-200 rounded-xl px-3 py-2 bg-white text-gray-700 shadow-sm focus:outline-none focus:border-indigo-400">
                  <option value="">All accounts</option>
                  {accounts.map(a => <option key={a.id} value={a.id}>{a.email_address}{a.is_primary ? ' ★' : ''}</option>)}
                </select>
              )}

              {/* Time range */}
              <div className="flex bg-gray-100 rounded-xl overflow-hidden">
                {TIME_RANGES.map(({ key, label }) => (
                  <button key={key} onClick={() => setSince(key)}
                    className={`px-3 py-2 text-xs font-semibold transition-all ${since === key ? 'bg-indigo-600 text-white shadow' : 'text-gray-500 hover:bg-gray-200'}`}>
                    {label}
                  </button>
                ))}
              </div>

              <button onClick={() => load(since, activeAccount)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-gray-200 text-xs font-semibold text-gray-600 hover:border-indigo-300 transition-all">
                <RefreshCw size={13} className={loading ? 'animate-spin text-indigo-500' : ''} />
                Refresh
              </button>

              <button onClick={handleBackfill} disabled={backfilling}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-all disabled:opacity-50">
                <Package size={13} className={backfilling ? 'animate-pulse' : ''} />
                {backfilling ? 'Detecting…' : 'Detect Products'}
              </button>

              {backfillResult && !backfillResult.error && (
                <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-100">
                  ✓ {backfillResult.backfilled} stored
                </span>
              )}
            </div>
          </div>

          {/* Tab bar */}
          <div ref={tabBarRef} className="flex gap-1 mt-5 border-b border-gray-100 -mb-px">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => setActiveTab(key)}
                className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-semibold transition-all rounded-t-lg ${activeTab === key ? 'text-indigo-600 bg-indigo-50/60' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'}`}>
                <Icon size={15} />
                {label}
                {activeTab === key && (
                  <motion.div layoutId="tabUnderline" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div className="max-w-[1400px] mx-auto px-6 py-6">
        <AnimatePresence mode="wait">
          <motion.div key={activeTab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.18 }}>
            {activeTab === 'overview'   && <TabOverview   data={data} loading={loading} />}
            {activeTab === 'pipeline'   && <TabPipeline   data={data} loading={loading} />}
            {activeTab === 'products'   && <TabProducts   data={data} loading={loading} />}
            {activeTab === 'resolution' && <TabResolution data={data} loading={loading} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

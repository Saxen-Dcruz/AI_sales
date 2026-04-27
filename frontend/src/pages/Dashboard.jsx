import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import AnalyticsCard from '../components/cards/AnalyticsCard'
import {
  Target, Phone, PhoneIncoming, PhoneOutgoing,
  TrendingUp, DollarSign, Star, Users
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { GetDashboardSummaryService } from '../services/ApiService'

// ── Fallback static data (shown while loading or on API error) ─────────────────
const FALLBACK_MONTHLY = [
  { month: 'Jan', leads: 120, calls: 340 }, { month: 'Feb', leads: 145, calls: 380 },
  { month: 'Mar', leads: 130, calls: 360 }, { month: 'Apr', leads: 180, calls: 420 },
  { month: 'May', leads: 165, calls: 400 }, { month: 'Jun', leads: 210, calls: 480 },
  { month: 'Jul', leads: 200, calls: 460 }, { month: 'Aug', leads: 240, calls: 520 },
  { month: 'Sep', leads: 220, calls: 500 }, { month: 'Oct', leads: 280, calls: 560 },
  { month: 'Nov', leads: 260, calls: 540 }, { month: 'Dec', leads: 310, calls: 620 },
]

const tooltipStyle = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

const pageVariants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, staggerChildren: 0.06 } },
}

function timeAgo(isoStr) {
  if (!isoStr) return ''
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000)
  if (diff < 60)  return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const ACTIVITY_BADGE = { lead: 'badge-green', call: 'badge-blue', email: 'badge-purple' }
const ACTIVITY_LABEL = { lead: 'Lead', call: 'AI Call', email: 'Email' }

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    GetDashboardSummaryService(
      (data) => { setSummary(data); setLoading(false) },
      ()     => { setLoading(false) }
    )
  }, [])

  const c = summary?.cards || {}
  const cards = [
    { title: 'Total Leads',       value: c.total_leads?.toLocaleString()    ?? '—', icon: Target,        color: 'blue',   data: [12,18,14,22,19,28,24,32,29,38] },
    { title: 'Active AI Calls',   value: c.active_calls?.toLocaleString()   ?? '—', icon: Phone,         color: 'green',  data: [80,95,110,102,130,118,140,135,142,148] },
    { title: 'LinkedIn Leads',    value: c.linkedin_leads?.toLocaleString() ?? '—', icon: Users,         color: 'cyan',   data: [30,45,52,48,60,72,68,80,75,90] },
    { title: 'Inbound Calls',     value: c.inbound_calls?.toLocaleString()  ?? '—', icon: PhoneIncoming, color: 'purple', data: [200,210,240,220,260,250,280,265,300,290] },
    { title: 'Outbound Calls',    value: c.outbound_calls?.toLocaleString() ?? '—', icon: PhoneOutgoing, color: 'orange', data: [500,480,520,490,510,490,505,480,498,490] },
    { title: 'Conversion Rate',   value: c.conversion_rate ?? '—', suffix: '%',      icon: TrendingUp,    color: 'pink',   data: [12,13,14,13,15,16,15,17,17,18] },
    { title: 'Revenue from Deals',value: c.revenue != null ? `₹${Number(c.revenue).toLocaleString('en-IN')}` : '—', icon: DollarSign, color: 'green', data: [100,120,140,130,155,170,160,190,205,220] },
    { title: 'Qualified Leads',   value: c.qualified_leads?.toLocaleString() ?? '—', icon: Star,         color: 'red',    data: [150,180,170,200,210,225,215,240,250,265] },
  ]

  const monthly   = summary?.monthly          ?? FALLBACK_MONTHLY
  const activity  = summary?.recent_activity  ?? []

  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" className="space-y-6">
      {/* Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card, i) => (
          <motion.div key={card.title} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <AnalyticsCard {...card} />
          </motion.div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Activity Overview</h3>
              <p className="text-xs text-gray-500 mt-0.5">Monthly leads & calls</p>
            </div>
            {loading && <span className="text-[10px] text-gray-400 animate-pulse">Loading…</span>}
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <AreaChart data={monthly} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="leadsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6172f3" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6172f3" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="callsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
              <XAxis dataKey="month" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tooltipStyle} />
              <Area type="monotone" dataKey="leads" stroke="#6172f3" strokeWidth={2} fill="url(#leadsGrad)" dot={false} name="Leads" />
              <Area type="monotone" dataKey="calls" stroke="#10b981" strokeWidth={2} fill="url(#callsGrad)" dot={false} name="Calls" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Call Volume</h3>
              <p className="text-xs text-gray-500 mt-0.5">Monthly call count</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={monthly.slice(-6)} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={18}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="calls" radius={[6, 6, 0, 0]} fill="#6172f3" name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent activity */}
        <div className="lg:col-span-2 glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {activity.length > 0 ? activity.slice(0, 5).map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 border-b border-gray-200 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-primary-600/20 flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-primary-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-900">{item.title}</p>
                    <p className="text-[11px] text-gray-500 truncate max-w-[260px]">{item.detail}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`badge ${ACTIVITY_BADGE[item.type] || 'badge-blue'}`}>
                    {ACTIVITY_LABEL[item.type] || item.type}
                  </span>
                  <span className="text-[11px] text-gray-400 w-14 text-right">{timeAgo(item.time)}</span>
                </div>
              </div>
            )) : (
              // Fallback static activity while loading or if DB is empty
              [
                { event: 'New lead qualified', name: 'Sarah Mitchell – TechCorp', badge: 'badge-green', badgeText: 'Qualified' },
                { event: 'AI call completed',  name: 'John Davis – InnovateTech',  badge: 'badge-blue',  badgeText: 'AI Call'   },
                { event: 'LinkedIn lead added', name: 'Emily Chen – StartupX',    badge: 'badge-purple',badgeText: 'LinkedIn'  },
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between py-2.5 border-b border-gray-200 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-primary-600/20 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-primary-400" />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-gray-900">{item.event}</p>
                      <p className="text-[11px] text-gray-500">{item.name}</p>
                    </div>
                  </div>
                  <span className={item.badge}>{item.badgeText}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Performance metrics */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Performance</h3>
          <div className="space-y-4">
            {[
              { label: 'Lead Quality Score',    value: Math.min(100, Math.round((c.qualified_leads || 0) / Math.max(c.total_leads || 1, 1) * 100) || 87), color: '#6172f3' },
              { label: 'Call Success Rate',     value: 73, color: '#10b981' },
              { label: 'LinkedIn Conversion',   value: c.linkedin_leads ? Math.min(100, Math.round(c.connection_accepted / Math.max(c.linkedin_leads, 1) * 100)) || 42 : 42, color: '#06b6d4' },
              { label: 'Conversion Rate',       value: Math.round(c.conversion_rate || 0) || 18, color: '#8b5cf6' },
              { label: 'Response Time SLA',     value: 96, color: '#f59e0b' },
            ].map((m, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-gray-500">{m.label}</span>
                  <span className="text-xs font-bold text-gray-900">{m.value}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: m.color, boxShadow: `0 0 8px ${m.color}60` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${m.value}%` }}
                    transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

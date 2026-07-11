import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Linkedin, Users, UserCheck, Send, MessageSquare, RefreshCw,
  TrendingUp, Activity, Zap, Clock,
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Cell,
} from 'recharts'
import { GetLinkedInStatsService, GetLinkedInBudgetService } from '../services/ApiService'

const LINKEDIN_BLUE = '#0077b5'

const tt = {
  contentStyle: {
    background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
    fontSize: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
  },
  cursor: { fill: 'rgba(0,0,0,0.03)' },
}

function KpiCard({ icon: Icon, label, value, sub, color, loading }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden bg-white rounded-2xl border border-gray-100 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="absolute top-0 right-0 w-24 h-24 rounded-full -translate-y-8 translate-x-8 opacity-[0.06]"
        style={{ background: color }} />
      <div className="p-2 rounded-xl w-fit mb-3" style={{ background: `${color}18` }}>
        <Icon size={18} style={{ color }} />
      </div>
      {loading ? (
        <div className="h-8 w-20 bg-gray-100 rounded-lg animate-pulse mb-1" />
      ) : (
        <p className="text-2xl font-black text-gray-900">{value ?? '—'}</p>
      )}
      <p className="text-xs font-semibold text-gray-500 mt-0.5">{label}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-1">{sub}</p>}
    </motion.div>
  )
}

function BudgetBar({ label, used, limit, color }) {
  const pct = limit > 0 ? Math.min(100, Math.round(used / limit * 100)) : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="font-semibold text-gray-700">{label}</span>
        <span className="text-gray-400">{used} / {limit}</span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ background: pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : color }}
        />
      </div>
      <p className="text-[11px] text-gray-400 mt-1">{limit - used} remaining today</p>
    </div>
  )
}

const FUNNEL_COLORS = ['#0077b5', '#3b9ed4', '#6172f3', '#10b981', '#f59e0b']

export default function LinkedInAnalytics({ hideHeader = false }) {
  const [stats, setStats] = useState(null)
  const [budget, setBudget] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    GetLinkedInStatsService(
      d => { setStats(d); setLoading(false) },
      () => setLoading(false)
    )
    GetLinkedInBudgetService(d => setBudget(d), () => {})
  }

  useEffect(() => { load() }, [])

  const funnelData = stats ? [
    { name: 'Discovered', value: stats.total_discovered, fill: FUNNEL_COLORS[0] },
    { name: 'Connection Sent', value: stats.total_discovered - stats.connection_not_sent, fill: FUNNEL_COLORS[1] },
    { name: 'Connected', value: stats.connection_accepted, fill: FUNNEL_COLORS[2] },
    { name: 'Messaged', value: stats.messages_sent, fill: FUNNEL_COLORS[3] },
    { name: 'Replied', value: stats.messages_replied, fill: FUNNEL_COLORS[4] },
  ] : []

  const barData = funnelData.map(d => ({ name: d.name, count: d.value }))

  const b = budget || {}

  return (
    <div className={hideHeader ? 'font-sans' : 'min-h-screen bg-gray-50 font-sans'}>
      <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">

        {/* Header */}
        <div className={`flex items-center justify-between ${hideHeader ? 'justify-end' : ''}`}>
          {!hideHeader && (
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ background: `${LINKEDIN_BLUE}18` }}>
                <Linkedin size={20} style={{ color: LINKEDIN_BLUE }} />
              </div>
              <div>
                <h1 className="text-xl font-black text-gray-900">LinkedIn Analytics</h1>
                <p className="text-xs text-gray-400 mt-0.5">Real-time outreach funnel & daily budget</p>
              </div>
            </div>
          )}
          <button onClick={load}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 text-sm font-semibold hover:bg-gray-100 transition-all">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiCard icon={Users} label="Profiles Discovered" value={stats?.total_discovered?.toLocaleString()}
            color={LINKEDIN_BLUE} loading={loading} />
          <KpiCard icon={Clock} label="Connection Pending"
            value={stats?.connection_pending?.toLocaleString()} color="#f59e0b" loading={loading} />
          <KpiCard icon={UserCheck} label="Connected"
            value={stats?.connection_accepted?.toLocaleString()}
            sub={`${stats?.connection_rate_pct ?? 0}% accept rate`}
            color="#10b981" loading={loading} />
          <KpiCard icon={Send} label="Messages Sent"
            value={stats?.messages_sent?.toLocaleString()} color="#6172f3" loading={loading} />
          <KpiCard icon={MessageSquare} label="Replied"
            value={stats?.messages_replied?.toLocaleString()}
            sub={`${stats?.reply_rate_pct ?? 0}% reply rate`}
            color="#8b5cf6" loading={loading} />
        </div>

        {/* Rates row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm flex items-center gap-5">
            <div className="w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: '#10b98118' }}>
              <TrendingUp size={24} style={{ color: '#10b981' }} />
            </div>
            <div>
              <p className="text-3xl font-black text-gray-900">{stats?.connection_rate_pct ?? '—'}%</p>
              <p className="text-sm font-semibold text-gray-500">Connection Accept Rate</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {stats?.connection_accepted ?? 0} accepted out of {(stats?.total_discovered ?? 0) - (stats?.connection_not_sent ?? 0)} sent
              </p>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm flex items-center gap-5">
            <div className="w-16 h-16 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: '#8b5cf618' }}>
              <Activity size={24} style={{ color: '#8b5cf6' }} />
            </div>
            <div>
              <p className="text-3xl font-black text-gray-900">{stats?.reply_rate_pct ?? '—'}%</p>
              <p className="text-sm font-semibold text-gray-500">Message Reply Rate</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {stats?.messages_replied ?? 0} replied out of {stats?.messages_sent ?? 0} sent
              </p>
            </div>
          </div>
        </div>

        {/* Funnel chart + Daily budget */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* Outreach Funnel */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
            <h3 className="text-sm font-black text-gray-900 mb-4">Outreach Funnel</h3>
            {loading ? (
              <div className="h-52 bg-gray-50 rounded-xl animate-pulse" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={barData} barSize={36}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280', fontWeight: 600 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                  <Tooltip {...tt} formatter={v => [v.toLocaleString(), 'Count']} />
                  <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                    {barData.map((entry, i) => (
                      <Cell key={i} fill={FUNNEL_COLORS[i] || LINKEDIN_BLUE} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Daily Budget */}
          <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-5">
              <Zap size={16} style={{ color: LINKEDIN_BLUE }} />
              <h3 className="text-sm font-black text-gray-900">Daily Budget</h3>
            </div>
            {budget ? (
              <div className="space-y-5">
                <BudgetBar
                  label="Connection Requests"
                  used={b.connections_used ?? 0}
                  limit={b.connections_limit ?? 15}
                  color={LINKEDIN_BLUE}
                />
                <BudgetBar
                  label="Messages (Today)"
                  used={b.messages_used_today ?? 0}
                  limit={40}
                  color="#6172f3"
                />
                <BudgetBar
                  label="Messages (This Week)"
                  used={b.messages_used_week ?? 0}
                  limit={90}
                  color="#8b5cf6"
                />
                <div className="pt-3 border-t border-gray-100 space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Connections left</span>
                    <span className="font-black text-emerald-600">{b.connections_remaining ?? 0}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Messages left today</span>
                    <span className="font-black text-emerald-600">{b.messages_remaining_today ?? 0}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Messages left this week</span>
                    <span className="font-black text-emerald-600">{b.messages_remaining_week ?? 0}</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {[1, 2, 3].map(i => <div key={i} className="h-8 bg-gray-100 rounded-lg animate-pulse" />)}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}

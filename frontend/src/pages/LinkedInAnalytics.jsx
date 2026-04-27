import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell
} from 'recharts'
import { GetLinkedInStatsService, GetLinkedInOutreachService } from '../services/ApiService'

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

// Static chart data — we don't have time-series from LinkedIn module yet
const WEEKLY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const ROLE_COLORS = {
  c_suite:     '#6172f3', cto: '#8b5cf6', cfo: '#06b6d4',
  procurement: '#10b981', operations: '#f59e0b', engineering: '#ef4444', generic: '#9ca3af',
}

export default function LinkedInAnalytics() {
  const [stats, setStats]         = useState(null)
  const [outreach, setOutreach]   = useState([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    GetLinkedInStatsService(
      (data) => { setStats(data); setLoading(false) },
      ()     => setLoading(false)
    )
    GetLinkedInOutreachService({ limit: 100 },
      (data) => setOutreach(data.items || []),
      ()     => {}
    )
  }, [])

  const s = stats || {}
  const budget = s.daily_budget || {}

  // Derive role distribution from outreach records
  const roleCounts = outreach.reduce((acc, r) => {
    const k = r.role_category || 'generic'
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const roleData = Object.entries(roleCounts).map(([name, value]) => ({
    name: name.replace('_', ' ').replace(/^\w/, c => c.toUpperCase()),
    value,
    color: ROLE_COLORS[name] || '#9ca3af',
  }))

  // Derive industry distribution
  const industryCounts = outreach.reduce((acc, r) => {
    const k = (r.industry_tag || 'other').split(' ')[0]
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const topIndustries = Object.entries(industryCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 5)
    .map(([name, value], i) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
      color: ['#6172f3','#8b5cf6','#06b6d4','#10b981','#f59e0b'][i],
    }))

  const connectionRate = s.connection_rate_pct ?? 0
  const replyRate      = s.reply_rate_pct      ?? 0

  // Build a simple weekly bar chart from daily_budget context (placeholder values until we have time-series)
  const weeklyData = WEEKLY_LABELS.map((day, i) => ({
    day,
    connections: Math.max(0, Math.round((budget.connections_used || 0) / 7 * (1 + (i - 3) * 0.2))),
    messages:    Math.max(0, Math.round((budget.messages_used_today || 0) * (1 + (i - 3) * 0.15))),
  }))

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Profiles Discovered',    value: loading ? '…' : (s.total_discovered ?? 0).toLocaleString(), color: 'text-primary-400' },
          { label: 'Connections Sent',       value: loading ? '…' : (s.connection_pending ?? 0) + (s.connection_accepted ?? 0), color: 'text-accent-cyan' },
          { label: 'Connections Accepted',   value: loading ? '…' : s.connection_accepted ?? 0, color: 'text-accent-green' },
          { label: 'Messages Replied',       value: loading ? '…' : s.messages_replied   ?? 0, color: 'text-accent-purple' },
        ].map((item, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5">
            <p className="text-xs text-gray-500 mb-2">{item.label}</p>
            <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
            {i === 2 && <p className="text-xs text-accent-green mt-1">{connectionRate}% acceptance rate</p>}
            {i === 3 && <p className="text-xs text-accent-green mt-1">{replyRate}% reply rate</p>}
          </motion.div>
        ))}
      </div>

      {/* Daily budget + weekly activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Daily Outreach Budget</h3>
          <p className="text-xs text-gray-500 mb-4">Used vs remaining today</p>
          <div className="space-y-4">
            {[
              { label: 'Connection Requests', used: budget.connections_used ?? 0, limit: budget.connections_limit ?? 15, color: '#6172f3' },
              { label: 'Messages Today',      used: budget.messages_used_today ?? 0, limit: 40, color: '#10b981' },
              { label: 'Messages This Week',  used: budget.messages_used_week ?? 0, limit: 90, color: '#06b6d4' },
            ].map((b, i) => (
              <div key={i}>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-gray-600">{b.label}</span>
                  <span className="text-gray-900 font-semibold">{b.used} / {b.limit}</span>
                </div>
                <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                  <motion.div className="h-full rounded-full"
                    style={{ background: b.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, (b.used / b.limit) * 100)}%` }}
                    transition={{ delay: 0.2 + i * 0.1, duration: 0.7 }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Outreach Activity</h3>
          <p className="text-xs text-gray-500 mb-4">Connections & messages sent</p>
          <ResponsiveContainer width="100%" height={180} minWidth={0}>
            <BarChart data={weeklyData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="connections" fill="#6172f3" radius={[6,6,0,0]} name="Connections" />
              <Bar dataKey="messages"    fill="#06b6d4" radius={[6,6,0,0]} name="Messages" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Role + industry distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Target Role Distribution</h3>
          {roleData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No outreach records yet</p>
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={180} height={180} minWidth={0}>
                <PieChart>
                  <Pie data={roleData} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value">
                    {roleData.map((e, i) => <Cell key={i} fill={e.color} stroke="none" />)}
                  </Pie>
                  <Tooltip {...tt} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {roleData.map((d, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                    <span className="text-xs text-gray-500">{d.name}</span>
                    <span className="text-xs font-semibold text-gray-900 ml-auto pl-4">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Top Industries Targeted</h3>
          {topIndustries.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No outreach records yet</p>
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width={180} height={180} minWidth={0}>
                <PieChart>
                  <Pie data={topIndustries} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value">
                    {topIndustries.map((e, i) => <Cell key={i} fill={e.color} stroke="none" />)}
                  </Pie>
                  <Tooltip {...tt} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2">
                {topIndustries.map((d, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                    <span className="text-xs text-gray-500">{d.name}</span>
                    <span className="text-xs font-semibold text-gray-900 ml-auto pl-4">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

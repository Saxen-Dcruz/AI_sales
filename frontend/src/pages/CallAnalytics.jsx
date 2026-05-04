import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { GetCallAnalyticsService, GetAllLeadsService } from '../services/ApiService'

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

export default function CallAnalytics() {
  const [analytics, setAnalytics] = useState(null)
  const [hotLeads, setHotLeads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      new Promise(res => GetCallAnalyticsService(res, () => res(null))),
      new Promise(res => GetAllLeadsService({ classification: 'HIGH', limit: 5 }, res, () => res(null))),
    ]).then(([analyticsData, leadsData]) => {
      setAnalytics(analyticsData)
      setHotLeads(leadsData?.items || [])
      setLoading(false)
    })
  }, [])

  const total = analytics?.total_calls ?? 0
  const completed = analytics?.by_status?.completed ?? 0
  const successRate = total > 0 ? Math.round((completed / total) * 100) : 0
  const avgDuration = analytics?.avg_duration_minutes
    ? `${Number(analytics.avg_duration_minutes).toFixed(1)}m`
    : '—'

  const directionData = analytics?.by_direction
    ? Object.entries(analytics.by_direction).map(([k, v]) => ({ name: k, calls: v }))
    : []

  const outcomeData = analytics?.by_outcome
    ? Object.entries(analytics.by_outcome).map(([k, v]) => ({ name: k.replace(/_/g, ' '), calls: v }))
    : []

  const sentimentData = analytics?.by_sentiment
    ? Object.entries(analytics.by_sentiment).map(([k, v]) => ({ name: k, calls: v }))
    : []

  if (loading) {
    return (
      <div className="flex justify-center py-20 text-gray-400 text-sm">Loading analytics...</div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Calls', value: total.toLocaleString(), sub: 'All time', color: 'text-primary-400' },
          { label: 'Avg Duration', value: avgDuration, sub: 'Per call', color: 'text-accent-cyan' },
          { label: 'Success Rate', value: `${successRate}%`, sub: 'Completed calls', color: 'text-accent-green' },
          { label: 'HIGH Leads', value: hotLeads.length, sub: 'Classification HIGH', color: 'text-accent-orange' },
        ].map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5">
            <p className="text-xs text-gray-500 mb-2">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-400 mt-1">{s.sub}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Inbound vs Outbound */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Direction Breakdown</h3>
          <p className="text-xs text-gray-500 mb-4">Inbound vs Outbound calls</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={directionData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="calls" fill="#6172f3" radius={[6, 6, 0, 0]} name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Outcome breakdown */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Outcome Breakdown</h3>
          <p className="text-xs text-gray-500 mb-4">Calls grouped by outcome</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={outcomeData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={32}>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="calls" radius={[6, 6, 0, 0]} fill="#8b5cf6" name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sentiment */}
        <div className="lg:col-span-2 glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Sentiment Distribution</h3>
          <p className="text-xs text-gray-500 mb-4">Call sentiment across all calls</p>
          <ResponsiveContainer width="100%" height={200} minWidth={0}>
            <AreaChart data={sentimentData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="sentGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" />
              <XAxis dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Area type="monotone" dataKey="calls" stroke="#10b981" strokeWidth={2.5} fill="url(#sentGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Status breakdown */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Status Breakdown</h3>
          <div className="space-y-3">
            {analytics?.by_status
              ? Object.entries(analytics.by_status).map(([status, count], i) => {
                  const pct = total > 0 ? Math.round((count / total) * 100) : 0
                  const colors = ['#6172f3', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']
                  return (
                    <div key={status}>
                      <div className="flex justify-between mb-1">
                        <span className="text-xs text-gray-500 capitalize">{status}</span>
                        <span className="text-xs font-bold text-gray-900">{count}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-gray-100">
                        <motion.div className="h-full rounded-full"
                          style={{ background: colors[i % colors.length] }}
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.3 + i * 0.1, duration: 0.8 }}
                        />
                      </div>
                    </div>
                  )
                })
              : <p className="text-xs text-gray-400">No data</p>
            }
          </div>
        </div>
      </div>

      {/* Hot leads */}
      {hotLeads.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">HIGH Classification Leads</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200">
                  {['Name', 'Company', 'Score', 'Next Action'].map(h => (
                    <th key={h} className="text-left py-2 px-3 text-gray-500 font-medium uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hotLeads.map((l, i) => (
                  <tr key={i} className="table-row">
                    <td className="py-3 px-3 text-gray-900 font-medium">{l.name}</td>
                    <td className="py-3 px-3 text-gray-500">{l.company_name || '—'}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-accent-orange">{l.engagement_score ?? 0}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-gray-100 max-w-16">
                          <div className="h-full rounded-full bg-accent-orange" style={{ width: `${l.engagement_score ?? 0}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-gray-500 max-w-xs truncate">{l.next_best_action || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  )
}

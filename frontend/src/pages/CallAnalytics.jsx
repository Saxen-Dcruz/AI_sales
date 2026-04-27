import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { GetCallAnalyticsService, GetLeadsService } from '../services/ApiService'

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

// Static fallback chart data until we have time-series call data
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export default function CallAnalytics() {
  const [analytics, setAnalytics] = useState(null)
  const [hotLeads, setHotLeads]   = useState([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    GetCallAnalyticsService(
      (data) => { setAnalytics(data); setLoading(false) },
      ()     => setLoading(false)
    )
    // High-classification leads as "hot leads"
    GetLeadsService({ classification: 'HIGH', limit: 5 },
      (data) => setHotLeads(data.items || []),
      ()     => {}
    )
  }, [])

  const a = analytics || {}
  const total      = a.total_calls ?? '—'
  const avgDurMin  = a.avg_duration_minutes ? `${a.avg_duration_minutes.toFixed(1)}m` : '—'
  const completed  = a.by_status?.completed ?? 0
  const successPct = total > 0 && completed !== '—' ? `${Math.round(completed / total * 100)}%` : '—'
  const hotCount   = a.by_intent?.ready_to_buy ?? 0

  // Build per-direction bar chart from by_direction
  const directionData = DAYS.map((day, i) => ({
    day,
    inbound:  Math.round((a.by_direction?.inbound  ?? 0) / 7 * (0.7 + i * 0.05)),
    outbound: Math.round((a.by_direction?.outbound ?? 0) / 7 * (0.7 + i * 0.05)),
  }))

  // Build intent/outcome bar from real data
  const intentData = Object.entries(a.by_intent || {}).map(([k, v]) => ({ name: k.replace(/_/g,' '), count: v }))
  const outcomeData = Object.entries(a.by_outcome || {}).map(([k, v]) => ({ name: k.replace(/_/g,' '), count: v }))

  // Sentiment breakdown
  const sentimentData = [
    { name: 'Positive',   value: a.by_sentiment?.POSITIVE   ?? 0, color: '#10b981' },
    { name: 'Neutral',    value: a.by_sentiment?.NEUTRAL    ?? 0, color: '#6172f3' },
    { name: 'Frustrated', value: a.by_sentiment?.FRUSTRATED ?? 0, color: '#ef4444' },
  ].filter(s => s.value > 0)

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Calls',   value: loading ? '…' : total,      sub: 'All time',            color: 'text-primary-400' },
          { label: 'Avg Duration',  value: loading ? '…' : avgDurMin,  sub: 'Per call',             color: 'text-accent-cyan' },
          { label: 'Success Rate',  value: loading ? '…' : successPct, sub: 'Completed calls',      color: 'text-accent-green' },
          { label: 'Ready to Buy',  value: loading ? '…' : hotCount,   sub: 'Intent = ready_to_buy',color: 'text-accent-orange' },
        ].map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
            <p className="text-[10px] text-gray-400 mt-0.5">{s.sub}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Inbound vs Outbound */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Inbound vs Outbound</h3>
          <p className="text-xs text-gray-500 mb-4">Estimated daily breakdown</p>
          <ResponsiveContainer width="100%" height={200} minWidth={0}>
            <BarChart data={directionData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="inbound"  fill="#6172f3" radius={[6,6,0,0]} name="Inbound" />
              <Bar dataKey="outbound" fill="#10b981" radius={[6,6,0,0]} name="Outbound" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Call outcomes */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Call Outcomes</h3>
          <p className="text-xs text-gray-500 mb-4">Distribution by outcome</p>
          {outcomeData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No call data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={200} minWidth={0}>
              <BarChart data={outcomeData} layout="vertical" margin={{ top: 0, right: 10, left: 60, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip {...tt} />
                <Bar dataKey="count" fill="#6172f3" radius={[0,6,6,0]} name="Calls" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Intent breakdown */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Intent (from transcripts)</h3>
          {intentData.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No transcript data yet</p>
          ) : (
            <div className="space-y-3">
              {intentData.map((item, i) => {
                const total_intents = intentData.reduce((a, b) => a + b.count, 0)
                const pct = total_intents ? Math.round(item.count / total_intents * 100) : 0
                const color = item.name === 'ready to buy' ? '#10b981' : item.name === 'not interested' ? '#ef4444' : '#6172f3'
                return (
                  <div key={i}>
                    <div className="flex justify-between text-xs mb-1.5">
                      <span className="text-gray-600 capitalize">{item.name}</span>
                      <span className="text-gray-900 font-semibold">{item.count} ({pct}%)</span>
                    </div>
                    <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                      <motion.div className="h-full rounded-full" style={{ background: color }}
                        initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.2 + i * 0.1, duration: 0.7 }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Sentiment + hot leads */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Sentiment & Hot Leads</h3>
          <div className="space-y-3 mb-4">
            {sentimentData.length === 0 ? (
              <p className="text-xs text-gray-400">No sentiment data yet</p>
            ) : sentimentData.map((s, i) => {
              const total_s = sentimentData.reduce((a, b) => a + b.value, 0)
              const pct = total_s ? Math.round(s.value / total_s * 100) : 0
              return (
                <div key={i}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-600">{s.name}</span>
                    <span className="text-gray-900 font-semibold">{s.value} ({pct}%)</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <motion.div className="h-full rounded-full" style={{ background: s.color }}
                      initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                      transition={{ delay: 0.2 + i * 0.1, duration: 0.7 }} />
                  </div>
                </div>
              )
            })}
          </div>
          <p className="text-xs font-semibold text-gray-700 mb-2">Top HIGH leads</p>
          {hotLeads.length === 0 ? (
            <p className="text-xs text-gray-400">No high-priority leads yet</p>
          ) : hotLeads.map((l) => (
            <div key={l.id} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-xs font-medium text-gray-900">{l.name}</p>
                <p className="text-[10px] text-gray-500">{l.company_name || '—'}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-gray-900">{l.engagement_score}</span>
                <span className="badge badge-green text-[10px]">HIGH</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

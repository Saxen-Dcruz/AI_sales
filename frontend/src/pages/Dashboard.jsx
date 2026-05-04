import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import AnalyticsCard from '../components/cards/AnalyticsCard'
import {
  Target, Phone, PhoneIncoming, PhoneOutgoing,
  TrendingUp, Star, Clock, Activity
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { GetCallAnalyticsService, GetAllLeadsService, GetLeadClassificationSummaryService } from '../services/ApiService'

const tooltipStyle = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

const pageVariants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, staggerChildren: 0.06 } },
}

export default function Dashboard() {
  const [callAnalytics, setCallAnalytics] = useState(null)
  const [leadTotal, setLeadTotal] = useState(null)
  const [classification, setClassification] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      new Promise(res => GetCallAnalyticsService(res, () => res(null))),
      new Promise(res => GetAllLeadsService({ limit: 1 }, res, () => res(null))),
      new Promise(res => GetLeadClassificationSummaryService(res, () => res(null))),
    ]).then(([callData, leadData, classData]) => {
      setCallAnalytics(callData)
      setLeadTotal(leadData?.total ?? null)
      setClassification(classData)
      setLoading(false)
    })
  }, [])

  const inbound = callAnalytics?.by_direction?.inbound ?? null
  const outbound = callAnalytics?.by_direction?.outbound ?? null
  const totalCalls = callAnalytics?.total_calls ?? null
  const avgDuration = callAnalytics?.avg_duration_minutes
    ? `${Number(callAnalytics.avg_duration_minutes).toFixed(1)}m`
    : null
  const highLeads = classification?.tiers?.HIGH?.count ?? null

  const cards = [
    { title: 'Total Leads', value: leadTotal !== null ? leadTotal.toLocaleString() : '—', change: null, changeLabel: 'all time', icon: Target, color: 'blue', data: [12,18,14,22,19,28,24,32,29,38] },
    { title: 'Total Calls', value: totalCalls !== null ? totalCalls.toLocaleString() : '—', change: null, changeLabel: 'all time', icon: Phone, color: 'green', data: [80,95,110,102,130,118,140,135,142,148] },
    { title: 'Inbound Calls', value: inbound !== null ? inbound.toLocaleString() : '—', change: null, changeLabel: 'all time', icon: PhoneIncoming, color: 'purple', data: [200,210,240,220,260,250,280,265,300,290] },
    { title: 'Outbound Calls', value: outbound !== null ? outbound.toLocaleString() : '—', change: null, changeLabel: 'all time', icon: PhoneOutgoing, color: 'orange', data: [500,480,520,490,510,490,505,480,498,490] },
    { title: 'Avg Call Duration', value: avgDuration ?? '—', change: null, changeLabel: 'per call', icon: Clock, color: 'cyan', data: [3,4,3,5,4,4,5,4,4,5] },
    { title: 'HIGH Leads', value: highLeads !== null ? highLeads.toLocaleString() : '—', change: null, changeLabel: 'classification', icon: Star, color: 'red', data: [150,180,170,200,210,225,215,240,250,265] },
    { title: 'Active Sessions', value: callAnalytics?.by_status?.active !== undefined ? callAnalytics.by_status.active.toLocaleString() : '—', change: null, changeLabel: 'right now', icon: Activity, color: 'pink', data: [1,2,1,3,2,4,3,2,3,2] },
    { title: 'Converted', value: callAnalytics?.by_outcome?.converted !== undefined ? callAnalytics.by_outcome.converted.toLocaleString() : '—', change: null, changeLabel: 'all time', icon: TrendingUp, color: 'green', data: [10,12,11,14,13,15,14,16,15,17] },
  ]

  const directionChartData = callAnalytics?.by_direction
    ? Object.entries(callAnalytics.by_direction).map(([k, v]) => ({ name: k, calls: v }))
    : []

  const outcomeChartData = callAnalytics?.by_outcome
    ? Object.entries(callAnalytics.by_outcome).map(([k, v]) => ({ name: k.replace(/_/g, ' '), calls: v }))
    : []

  const classificationItems = classification?.tiers
    ? Object.entries(classification.tiers).map(([tier, data]) => ({
        label: tier,
        value: data.avg_score ? Math.round(data.avg_score) : 0,
        color: tier === 'HIGH' ? '#10b981' : tier === 'MEDIUM' ? '#f59e0b' : tier === 'LOW' ? '#ef4444' : '#6172f3',
      }))
    : []

  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" className="space-y-6">
      {/* Cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card, i) => (
          <motion.div key={card.title} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
            <AnalyticsCard {...card} />
          </motion.div>
        ))}
      </div>

      {loading && (
        <div className="text-center text-xs text-gray-400 py-2">Loading live data...</div>
      )}

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Direction chart */}
        <div className="lg:col-span-2 glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Call Direction</h3>
              <p className="text-xs text-gray-500 mt-0.5">Inbound vs Outbound</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={directionChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="40%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="calls" radius={[6, 6, 0, 0]} fill="#6172f3" name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Outcome chart */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Call Outcomes</h3>
              <p className="text-xs text-gray-500 mt-0.5">By outcome type</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={outcomeChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={14}>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#5e5f6e', fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="calls" radius={[4, 4, 0, 0]} fill="#10b981" name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Lead classification */}
        <div className="lg:col-span-2 glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Lead Classification</h3>
          {classificationItems.length > 0 ? (
            <div className="space-y-4">
              {classificationItems.map((item, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-gray-500">{item.label} — Avg Score</span>
                    <span className="text-xs font-bold text-gray-900">{item.value}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: item.color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${item.value}%` }}
                      transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">No classification data yet.</p>
          )}
        </div>

        {/* Call status breakdown */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Status</h3>
          <div className="space-y-3">
            {callAnalytics?.by_status
              ? Object.entries(callAnalytics.by_status).map(([status, count], i) => {
                  const colors = ['#6172f3', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']
                  const pct = totalCalls > 0 ? Math.round((count / totalCalls) * 100) : 0
                  return (
                    <div key={status}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500 capitalize">{status}</span>
                        <span className="text-xs font-bold text-gray-900">{count}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{ background: colors[i % colors.length] }}
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                        />
                      </div>
                    </div>
                  )
                })
              : <p className="text-xs text-gray-400">No call data yet.</p>
            }
          </div>
        </div>
      </div>
    </motion.div>
  )
}

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Bot, Phone, Clock, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
import { GetAllCallsService, GetCallAnalyticsService } from '../services/ApiService'

const outcomeClass = {
  interested: 'badge-green',
  converted: 'badge-green',
  follow_up: 'badge-blue',
  not_interested: 'badge-red',
  no_answer: 'badge-red',
  unknown: 'badge-orange',
}

function statusIcon(status) {
  if (status === 'completed') return <CheckCircle size={13} className="text-accent-green" />
  if (status === 'missed' || status === 'failed') return <XCircle size={13} className="text-accent-red" />
  return <AlertCircle size={13} className="text-accent-orange" />
}

function formatSeconds(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}m ${sec}s`
}

function relativeTime(iso) {
  if (!iso) return '—'
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function AICallLogs() {
  const [calls, setCalls] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = () => {
    setLoading(true)
    Promise.all([
      new Promise(res => GetAllCallsService({ limit: 50 }, res, () => res(null))),
      new Promise(res => GetCallAnalyticsService(res, () => res(null))),
    ]).then(([callsData, analyticsData]) => {
      setCalls(callsData?.items || [])
      setAnalytics(analyticsData)
      setLoading(false)
    })
  }

  useEffect(() => { fetchData() }, [])

  const stats = [
    { label: 'Total Calls', value: analytics?.total_calls ?? '—', color: 'text-primary-400', icon: Bot },
    { label: 'Completed', value: analytics?.by_status?.completed ?? '—', color: 'text-accent-green', icon: CheckCircle },
    { label: 'Missed / Failed', value: ((analytics?.by_status?.missed ?? 0) + (analytics?.by_status?.failed ?? 0)) || '—', color: 'text-accent-red', icon: XCircle },
    { label: 'Avg Duration', value: analytics?.avg_duration_minutes ? `${Number(analytics.avg_duration_minutes).toFixed(1)}m` : '—', color: 'text-accent-cyan', icon: Clock },
  ]

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5 flex items-center gap-4">
            <div className="p-2.5 rounded-xl bg-gray-100">
              <s.icon size={18} className={s.color} />
            </div>
            <div>
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          </motion.div>
        ))}
      </div>

      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-gray-900">Call Log</h3>
          <button onClick={fetchData} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-all">
            <RefreshCw size={14} />
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12 text-gray-400 text-sm">Loading calls...</div>
        ) : calls.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">No calls logged yet.</div>
        ) : (
          <div className="space-y-3">
            {calls.map((call, i) => (
              <motion.div key={call.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-all hover:bg-gray-50">
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-primary-600/20 flex items-center justify-center flex-shrink-0">
                      <Bot size={16} className="text-primary-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-gray-900">{call.phone_number || 'Unknown'}</span>
                        <span className="text-[10px] text-gray-400">·</span>
                        <span className="text-[10px] text-gray-500 capitalize">{call.direction}</span>
                        {call.intent && (
                          <>
                            <span className="text-[10px] text-gray-400">·</span>
                            <span className="text-[10px] text-gray-500">{call.intent}</span>
                          </>
                        )}
                      </div>
                      <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                        {call.ai_summary || call.transcript?.slice(0, 120) || 'No summary yet'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="flex items-center gap-1 text-gray-500">
                      <Phone size={12} />
                      <span className="text-xs">{formatSeconds(call.duration_seconds)}</span>
                    </div>
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-lg bg-gray-100 text-gray-500 capitalize">
                      {call.sentiment || '—'}
                    </span>
                    <div className="flex items-center gap-1">
                      {statusIcon(call.status)}
                      <span className={`badge ${outcomeClass[call.outcome] || 'badge-blue'}`}>
                        {call.outcome?.replace(/_/g, ' ') || call.status}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-500 w-14 text-right">{relativeTime(call.started_at)}</span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

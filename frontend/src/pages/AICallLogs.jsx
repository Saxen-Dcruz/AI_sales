import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Bot, Phone, Clock, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'
import { GetCallsService, GetCallAnalyticsService } from '../services/ApiService'

const statusIcon = {
  completed: <CheckCircle size={13} className="text-accent-green" />,
  missed:    <XCircle size={13} className="text-accent-red" />,
  failed:    <XCircle size={13} className="text-accent-red" />,
  active:    <AlertCircle size={13} className="text-accent-orange" />,
  new:       <AlertCircle size={13} className="text-accent-orange" />,
}
const statusBadge = {
  completed: 'badge-green', missed: 'badge-red', failed: 'badge-red',
  active: 'badge-orange', new: 'badge-orange', voicemail: 'badge-blue',
}

function fmtDuration(secs) {
  if (!secs) return '—'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}m ${s}s`
}

function timeAgo(iso) {
  if (!iso) return ''
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60)   return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function AICallLogs() {
  const [logs, setLogs]           = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading]     = useState(true)

  const fetchData = () => {
    setLoading(true)
    GetCallsService({ limit: 20, page: 1 },
      (data) => { setLogs(data.items || []); setLoading(false) },
      ()     => setLoading(false)
    )
    GetCallAnalyticsService(
      (data) => setAnalytics(data),
      ()     => {}
    )
  }

  useEffect(() => { fetchData() }, [])

  const a = analytics || {}
  const totalCalls   = a.total_calls ?? '—'
  const successful   = a.by_status?.completed ?? '—'
  const failed       = (a.by_status?.missed ?? 0) + (a.by_status?.failed ?? 0) || '—'
  const avgDuration  = a.avg_duration_minutes ? `${a.avg_duration_minutes.toFixed(1)}m` : '—'

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Calls',   value: totalCalls,  color: 'text-primary-400',  icon: Bot },
          { label: 'Completed',     value: successful,  color: 'text-accent-green', icon: CheckCircle },
          { label: 'Missed/Failed', value: failed,      color: 'text-accent-red',   icon: XCircle },
          { label: 'Avg Duration',  value: avgDuration, color: 'text-accent-cyan',  icon: Clock },
        ].map((s, i) => (
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
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Call Log</h3>
            <p className="text-xs text-gray-500 mt-0.5">Most recent calls</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-blue">Live</span>
            <button onClick={fetchData}
              className={`p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-all ${loading ? 'opacity-50' : ''}`}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        <div className="space-y-3">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="p-4 rounded-xl border border-gray-200 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-9 h-9 rounded-xl bg-gray-100 flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-gray-100 rounded w-1/3" />
                    <div className="h-2 bg-gray-100 rounded w-2/3" />
                  </div>
                </div>
              </div>
            ))
          ) : logs.length === 0 ? (
            <p className="text-center text-sm text-gray-400 py-8">No calls recorded yet</p>
          ) : (
            logs.map((log, i) => {
              const contact = log.lead_id ? `Lead #${String(log.lead_id).slice(0, 8)}` : log.phone_number || 'Unknown'
              const outcome = log.outcome || log.status || 'unknown'
              return (
                <motion.div key={log.id}
                  initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  className="p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-all hover:bg-gray-50 cursor-pointer">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div className="w-9 h-9 rounded-xl bg-primary-600/20 flex items-center justify-center flex-shrink-0">
                        <Bot size={16} className="text-primary-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-gray-900">{contact}</span>
                          {log.detected_product_name && (
                            <>
                              <span className="text-[10px] text-gray-400">·</span>
                              <span className="text-[10px] text-gray-500">{log.detected_product_name}</span>
                            </>
                          )}
                        </div>
                        <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                          {log.ai_summary || `${log.direction} call`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <div className="flex items-center gap-1 text-gray-500">
                        <Phone size={12} />
                        <span className="text-xs">{fmtDuration(log.duration_seconds)}</span>
                      </div>
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-lg bg-gray-100 text-gray-500 capitalize">
                        {log.direction}
                      </span>
                      <div className="flex items-center gap-1">
                        {statusIcon[log.status] || statusIcon.new}
                        <span className={`badge ${statusBadge[log.status] || 'badge-blue'} capitalize`}>{outcome}</span>
                      </div>
                      <span className="text-[10px] text-gray-500 w-14 text-right">
                        {timeAgo(log.started_at || log.created_at)}
                      </span>
                    </div>
                  </div>
                </motion.div>
              )
            })
          )}
        </div>
      </div>
    </motion.div>
  )
}

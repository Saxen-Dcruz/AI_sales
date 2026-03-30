import { motion } from 'framer-motion'
import { Bot, Phone, Clock, User, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

const logs = [
  { id: 'CALL-001', agent: 'Alpha', contact: 'Sarah Mitchell', company: 'TechCorp', duration: '5m 42s', status: 'Success', outcome: 'Demo Booked', time: '2m ago', transcript: 'Lead confirmed budget. Scheduled product demo for next Tuesday.' },
  { id: 'CALL-002', agent: 'Beta', contact: 'James Liu', company: 'DataSys', duration: '3m 18s', status: 'Success', outcome: 'Follow Up', time: '8m ago', transcript: 'Interested in Growth plan. Needs pricing breakdown.' },
  { id: 'CALL-003', agent: 'Gamma', contact: 'Anon Call', company: 'Unknown', duration: '0m 48s', status: 'Failed', outcome: 'No Answer', time: '14m ago', transcript: 'No answer. Left voicemail.' },
  { id: 'CALL-004', agent: 'Alpha', contact: 'Tom Baker', company: 'AI Ventures', duration: '7m 05s', status: 'Success', outcome: 'Qualified', time: '22m ago', transcript: 'Decision maker confirmed. Very high interest. High priority lead.' },
  { id: 'CALL-005', agent: 'Delta', contact: 'Priya Patel', company: 'FinTech One', duration: '4m 30s', status: 'Pending', outcome: 'Callback Requested', time: '35m ago', transcript: 'Requested callback tomorrow 10am. Note: compliance questions.' },
  { id: 'CALL-006', agent: 'Beta', contact: 'Chris Evans', company: 'BuildFast', duration: '2m 12s', status: 'Failed', outcome: 'Hung Up', time: '1h ago', transcript: 'Call ended prematurely. Contact hung up. Retry scheduled.' },
  { id: 'CALL-007', agent: 'Gamma', contact: 'Anna Lee', company: 'MediaTech', duration: '6m 50s', status: 'Success', outcome: 'Proposal Stage', time: '1.5h ago', transcript: 'Very warm lead. Budget approved internally. Sending proposal today.' },
]

const statusIcon = {
  Success: <CheckCircle size={13} className="text-accent-green" />,
  Failed: <XCircle size={13} className="text-accent-red" />,
  Pending: <AlertCircle size={13} className="text-accent-orange" />,
}
const statusBadge = {
  Success: 'badge-green',
  Failed: 'badge-red',
  Pending: 'badge-orange',
}

export default function AICallLogs() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total AI Calls', value: '1,248', color: 'text-primary-400', icon: Bot },
          { label: 'Successful', value: '1,048', color: 'text-accent-green', icon: CheckCircle },
          { label: 'Failed', value: '142', color: 'text-accent-red', icon: XCircle },
          { label: 'Avg Duration', value: '4.2m', color: 'text-accent-cyan', icon: Clock },
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
          <h3 className="text-sm font-semibold text-gray-900">AI Call Log</h3>
          <span className="badge badge-blue">Live</span>
        </div>
        <div className="space-y-3">
          {logs.map((log, i) => (
            <motion.div key={log.id}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-all hover:bg-gray-50 cursor-pointer">
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                {/* Left */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-primary-600/20 flex items-center justify-center flex-shrink-0">
                    <Bot size={16} className="text-primary-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-gray-900">{log.contact}</span>
                      <span className="text-[10px] text-gray-400">·</span>
                      <span className="text-[10px] text-gray-500">{log.company}</span>
                    </div>
                    <p className="text-[10px] text-gray-500 mt-0.5 truncate">{log.transcript}</p>
                  </div>
                </div>

                {/* Right */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className="flex items-center gap-1 text-gray-500">
                    <Phone size={12} />
                    <span className="text-xs">{log.duration}</span>
                  </div>
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-lg bg-gray-100 text-gray-500">{log.agent}</span>
                  <div className="flex items-center gap-1">
                    {statusIcon[log.status]}
                    <span className={`badge ${statusBadge[log.status]}`}>{log.outcome}</span>
                  </div>
                  <span className="text-[10px] text-gray-500 w-12 text-right">{log.time}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

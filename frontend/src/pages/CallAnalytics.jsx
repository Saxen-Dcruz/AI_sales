import { motion } from 'framer-motion'
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'

const callsPerDay = [
  { day: 'Mon', inbound: 145, outbound: 380 },
  { day: 'Tue', inbound: 182, outbound: 440 },
  { day: 'Wed', inbound: 164, outbound: 410 },
  { day: 'Thu', inbound: 221, outbound: 520 },
  { day: 'Fri', inbound: 198, outbound: 490 },
  { day: 'Sat', inbound: 88, outbound: 190 },
  { day: 'Sun', inbound: 62, outbound: 130 },
]

const durationData = [
  { range: '<1m', count: 320 }, { range: '1-2m', count: 580 }, { range: '2-5m', count: 740 },
  { range: '5-10m', count: 490 }, { range: '>10m', count: 220 },
]

const successRate = [
  { week: 'W1', rate: 68 }, { week: 'W2', rate: 72 }, { week: 'W3', rate: 69 },
  { week: 'W4', rate: 78 }, { week: 'W5', rate: 82 }, { week: 'W6', rate: 80 },
  { week: 'W7', rate: 85 }, { week: 'W8', rate: 84 },
]

const agents = [
  { name: 'AI Agent Alpha', calls: 1240, success: 89, color: '#6172f3' },
  { name: 'AI Agent Beta', calls: 980, success: 82, color: '#8b5cf6' },
  { name: 'AI Agent Gamma', calls: 856, success: 77, color: '#06b6d4' },
  { name: 'AI Agent Delta', calls: 720, success: 74, color: '#10b981' },
]

const hotLeads = [
  { name: 'Sarah Mitchell', company: 'TechCorp', score: 96, status: 'Ready to Close' },
  { name: 'James Liu', company: 'DataSys', score: 92, status: 'Follow Up' },
  { name: 'Maria Gonzalez', company: 'CloudBase', score: 88, status: 'In Negotiation' },
  { name: 'Tom Baker', company: 'AI Ventures', score: 85, status: 'Demo Scheduled' },
  { name: 'Priya Patel', company: 'FinTech One', score: 83, status: 'Proposal Sent' },
]

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

export default function CallAnalytics() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Calls Today', value: '1,060', sub: 'Inbound + Outbound', color: 'text-primary-400' },
          { label: 'Avg Duration', value: '4.2m', sub: 'Per call average', color: 'text-accent-cyan' },
          { label: 'Success Rate', value: '85%', sub: 'Calls with outcome', color: 'text-accent-green' },
          { label: 'Hot Leads', value: '47', sub: 'Score ≥ 80', color: 'text-accent-orange' },
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
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Inbound vs Outbound</h3>
          <p className="text-xs text-gray-500 mb-4">Calls per day this week</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={callsPerDay} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="inbound" fill="#6172f3" radius={[6, 6, 0, 0]} name="Inbound" />
              <Bar dataKey="outbound" fill="#06b6d4" radius={[6, 6, 0, 0]} name="Outbound" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Call duration */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Call Duration Distribution</h3>
          <p className="text-xs text-gray-500 mb-4">Calls grouped by duration</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={durationData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={36}>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="range" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} fill="#8b5cf6" name="Calls" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Success rate timeline */}
        <div className="lg:col-span-2 glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Call Success Rate Timeline</h3>
          <p className="text-xs text-gray-500 mb-4">Weekly success rate trend</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={successRate} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" />
              <XAxis dataKey="week" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[60, 100]} tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip {...tt} formatter={v => [`${v}%`, 'Success Rate']} />
              <Area type="monotone" dataKey="rate" stroke="#10b981" strokeWidth={2.5} fill="url(#successGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Agent performance */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Agent Performance</h3>
          <div className="space-y-4">
            {agents.map((a, i) => (
              <div key={i}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-gray-500">{a.name}</span>
                  <span className="text-xs font-bold text-gray-900">{a.success}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100">
                  <motion.div className="h-full rounded-full"
                    style={{ background: a.color, boxShadow: `0 0 6px ${a.color}60` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${a.success}%` }}
                    transition={{ delay: 0.3 + i * 0.1, duration: 0.8 }}
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-0.5">{a.calls.toLocaleString()} calls</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Hot leads */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">🔥 Hot Leads</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                {['Name', 'Company', 'Score', 'Status'].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-gray-500 font-medium uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hotLeads.map((l, i) => (
                <tr key={i} className="table-row">
                  <td className="py-3 px-3 text-gray-900 font-medium">{l.name}</td>
                  <td className="py-3 px-3 text-gray-500">{l.company}</td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-accent-orange">{l.score}</span>
                      <div className="flex-1 h-1.5 rounded-full bg-gray-100 max-w-16">
                        <div className="h-full rounded-full bg-accent-orange" style={{ width: `${l.score}%` }} />
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3"><span className="badge badge-green">{l.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}

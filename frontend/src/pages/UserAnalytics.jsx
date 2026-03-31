import { motion } from 'framer-motion'
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar
} from 'recharts'

const signupData = [
  { date: 'Mar 1', signups: 42 }, { date: 'Mar 2', signups: 58 }, { date: 'Mar 3', signups: 51 },
  { date: 'Mar 4', signups: 73 }, { date: 'Mar 5', signups: 68 }, { date: 'Mar 6', signups: 88 },
  { date: 'Mar 7', signups: 79 }, { date: 'Mar 8', signups: 92 }, { date: 'Mar 9', signups: 105 },
  { date: 'Mar 10', signups: 98 }, { date: 'Mar 11', signups: 114 }, { date: 'Mar 12', signups: 120 },
]

const engagementData = [
  { day: 'Mon', sessions: 840, duration: 12.4 }, { day: 'Tue', sessions: 920, duration: 14.1 },
  { day: 'Wed', sessions: 880, duration: 13.5 }, { day: 'Thu', sessions: 1050, duration: 16.2 },
  { day: 'Fri', sessions: 960, duration: 15.0 }, { day: 'Sat', sessions: 420, duration: 8.4 },
  { day: 'Sun', sessions: 380, duration: 7.8 },
]

const featureUsage = [
  { feature: 'Lead Gen', usage: 92, color: '#6172f3' },
  { feature: 'AI Calls', usage: 78, color: '#8b5cf6' },
  { feature: 'LinkedIn', usage: 85, color: '#0077b5' },
  { feature: 'Analytics', usage: 71, color: '#06b6d4' },
  { feature: 'Reports', usage: 58, color: '#10b981' },
  { feature: 'Settings', usage: 34, color: '#f59e0b' },
]

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

export default function UserAnalytics() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Active Users', value: '3,842', sub: '+124 today', color: 'text-primary-400' },
          { label: 'Daily Signups', value: '120', sub: '+18% vs yesterday', color: 'text-accent-green' },
          { label: 'Avg Session', value: '14.8m', sub: 'Platform usage', color: 'text-accent-cyan' },
          { label: 'Retention Rate', value: '78.4%', sub: '30-day retention', color: 'text-accent-purple' },
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
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Daily Signups</h3>
          <p className="text-xs text-gray-500 mb-4">New user registrations this month</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <AreaChart data={signupData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="signGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" />
              <XAxis dataKey="date" tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Area type="monotone" dataKey="signups" stroke="#8b5cf6" strokeWidth={2} fill="url(#signGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">User Engagement</h3>
          <p className="text-xs text-gray-500 mb-4">Sessions and avg duration per day</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={engagementData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="35%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="sessions" fill="#6172f3" radius={[6, 6, 0, 0]} name="Sessions" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Feature Usage Heatmap</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {featureUsage.map((f, i) => (
            <div key={i} className="flex flex-col items-center gap-2">
              <div className="relative w-full h-24 rounded-xl flex items-end justify-center overflow-hidden bg-gray-50">
                <motion.div
                  className="w-full rounded-xl"
                  style={{ background: `linear-gradient(to top, ${f.color}, ${f.color}60)`, boxShadow: `0 0 12px ${f.color}40` }}
                  initial={{ height: 0 }}
                  animate={{ height: `${f.usage}%` }}
                  transition={{ delay: 0.3 + i * 0.08, duration: 0.8, ease: 'easeOut' }}
                />
              </div>
              <span className="text-xs text-gray-500 font-medium">{f.feature}</span>
              <span className="text-xs font-bold" style={{ color: f.color }}>{f.usage}%</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

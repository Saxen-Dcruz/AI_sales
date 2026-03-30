import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'

const sentimentData = [
  { month: 'Jan', positive: 62, neutral: 24, negative: 14 },
  { month: 'Feb', positive: 68, neutral: 20, negative: 12 },
  { month: 'Mar', positive: 64, neutral: 22, negative: 14 },
  { month: 'Apr', positive: 72, neutral: 18, negative: 10 },
  { month: 'May', positive: 75, neutral: 17, negative: 8 },
  { month: 'Jun', positive: 78, neutral: 15, negative: 7 },
]

const categories = [
  { name: 'AI Quality', value: 32, color: '#6172f3' },
  { name: 'Speed', value: 24, color: '#10b981' },
  { name: 'UI/UX', value: 18, color: '#06b6d4' },
  { name: 'Pricing', value: 14, color: '#f59e0b' },
  { name: 'Support', value: 12, color: '#8b5cf6' },
]

const complaints = [
  { text: 'AI responses sometimes feel too generic', count: 48, sentiment: 'negative' },
  { text: 'Longer call recordings upload time', count: 34, sentiment: 'negative' },
  { text: 'Filter options in lead table need more depth', count: 28, sentiment: 'negative' },
  { text: 'Would like bulk actions on leads', count: 25, sentiment: 'negative' },
]

const requests = [
  { text: 'CRM integration (Salesforce, HubSpot)', count: 124, sentiment: 'positive' },
  { text: 'Email automation sequences', count: 98, sentiment: 'positive' },
  { text: 'White-label reporting', count: 76, sentiment: 'positive' },
  { text: 'Custom AI voice personas', count: 65, sentiment: 'positive' },
  { text: 'Multi-language support', count: 54, sentiment: 'positive' },
]

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
}

export default function UserFeedback() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Avg Rating', value: '4.6★', color: 'text-accent-orange' },
          { label: 'Positive Sentiment', value: '78%', color: 'text-accent-green' },
          { label: 'Feedback This Month', value: '1,240', color: 'text-primary-400' },
          { label: 'NPS Score', value: '72', color: 'text-accent-cyan' },
        ].map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5">
            <p className="text-xs text-gray-500 mb-2">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Sentiment bar */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Sentiment Analysis</h3>
          <p className="text-xs text-gray-500 mb-4">Monthly positive / neutral / negative breakdown</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={sentimentData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip {...tt} formatter={v => [`${v}%`]} />
              <Bar dataKey="positive" fill="#10b981" radius={[4, 4, 0, 0]} name="Positive" stackId="a" />
              <Bar dataKey="neutral" fill="#6172f3" radius={[0, 0, 0, 0]} name="Neutral" stackId="a" />
              <Bar dataKey="negative" fill="#ef4444" radius={[4, 4, 0, 0]} name="Negative" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category donut */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Feedback Categories</h3>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={180} height={180}>
              <PieChart>
                <Pie data={categories} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  paddingAngle={3} dataKey="value">
                  {categories.map((e, i) => <Cell key={i} fill={e.color} stroke="none" />)}
                </Pie>
                <Tooltip {...tt} formatter={v => [`${v}%`, '']} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {categories.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                  <span className="text-xs text-gray-500">{d.name}</span>
                  <span className="text-xs font-bold text-gray-900 ml-auto pl-4">{d.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Complaints */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">🔴 Top Complaints</h3>
          <div className="space-y-3">
            {complaints.map((c, i) => (
              <div key={i} className="p-3 rounded-xl bg-accent-red/5 border border-accent-red/10">
                <p className="text-xs text-gray-600">{c.text}</p>
                <p className="text-[10px] text-accent-red mt-1">{c.count} reports</p>
              </div>
            ))}
          </div>
        </div>

        {/* Feature requests */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">✨ Top Feature Requests</h3>
          <div className="space-y-3">
            {requests.map((r, i) => (
              <div key={i} className="p-3 rounded-xl bg-accent-green/5 border border-accent-green/10">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-gray-600">{r.text}</p>
                  <span className="badge badge-green ml-2 flex-shrink-0">{r.count} votes</span>
                </div>
                <div className="mt-2 h-1 rounded-full bg-gray-100">
                  <motion.div className="h-full rounded-full bg-accent-green"
                    initial={{ width: 0 }}
                    animate={{ width: `${(r.count / 124) * 100}%` }}
                    transition={{ delay: 0.3 + i * 0.1, duration: 0.8 }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

import { motion } from 'framer-motion'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell, Legend
} from 'recharts'

const dailyLeads = [
  { day: 'Mon', scraped: 320, posts: 45 },
  { day: 'Tue', scraped: 410, posts: 62 },
  { day: 'Wed', scraped: 385, posts: 55 },
  { day: 'Thu', scraped: 490, posts: 78 },
  { day: 'Fri', scraped: 445, posts: 69 },
  { day: 'Sat', scraped: 210, posts: 30 },
  { day: 'Sun', scraped: 175, posts: 22 },
]

const profileSuccess = [
  { day: 'Mon', success: 78 }, { day: 'Tue', success: 82 }, { day: 'Wed', success: 75 },
  { day: 'Thu', success: 88 }, { day: 'Fri', success: 85 }, { day: 'Sat', success: 79 }, { day: 'Sun', success: 72 },
]

const industryData = [
  { name: 'Technology', value: 38, color: '#6172f3' },
  { name: 'Finance', value: 22, color: '#8b5cf6' },
  { name: 'Healthcare', value: 16, color: '#06b6d4' },
  { name: 'Retail', value: 12, color: '#10b981' },
  { name: 'Other', value: 12, color: '#f59e0b' },
]

const sourceData = [
  { name: 'LinkedIn', value: 52, color: '#0077b5' },
  { name: 'Inbound', value: 24, color: '#6172f3' },
  { name: 'Sheets', value: 14, color: '#10b981' },
  { name: 'Referral', value: 10, color: '#f59e0b' },
]

const tt = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

const pageVar = { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 } }

export default function LinkedInAnalytics() {
  return (
    <motion.div variants={pageVar} initial="initial" animate="animate" className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Leads Scraped Today', value: '490', change: '+12%', color: 'text-primary-400' },
          { label: 'Posts Generated', value: '78', change: '+8%', color: 'text-accent-cyan' },
          { label: 'Profile Success Rate', value: '88%', change: '+3%', color: 'text-accent-green' },
          { label: 'Connection Requests', value: '1,240', change: '+18%', color: 'text-accent-purple' },
        ].map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
            className="glass-card p-5">
            <p className="text-xs text-gray-500 mb-2">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-accent-green mt-1">{s.change} this week</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Leads + posts bar */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Daily Lead Scraping</h3>
          <p className="text-xs text-gray-500 mb-4">Scraped leads and posts per day</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={dailyLeads} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="30%">
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tt} />
              <Bar dataKey="scraped" fill="#6172f3" radius={[6, 6, 0, 0]} name="Scraped" />
              <Bar dataKey="posts" fill="#06b6d4" radius={[6, 6, 0, 0]} name="Posts" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Profile success line */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Profile Scraping Success Rate</h3>
          <p className="text-xs text-gray-500 mb-4">% of successful profile scrapes</p>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <LineChart data={profileSuccess} margin={{ top: 0, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="rgba(0,0,0,0.06)" strokeDasharray="4 4" />
              <XAxis dataKey="day" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[60, 100]} tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip {...tt} formatter={v => [`${v}%`, 'Success Rate']} />
              <Line type="monotone" dataKey="success" stroke="#10b981" strokeWidth={2.5}
                dot={{ fill: '#10b981', r: 4, strokeWidth: 0 }}
                activeDot={{ r: 6, fill: '#10b981', stroke: '#fff', strokeWidth: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Industry donut */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Industry Distribution</h3>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={180} height={180} minWidth={0}>
              <PieChart>
                <Pie data={industryData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  paddingAngle={3} dataKey="value">
                  {industryData.map((e, i) => <Cell key={i} fill={e.color} stroke="none" />)}
                </Pie>
                <Tooltip {...tt} formatter={v => [`${v}%`, '']} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {industryData.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                  <span className="text-xs text-gray-500">{d.name}</span>
                  <span className="text-xs font-semibold text-gray-900 ml-auto pl-4">{d.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Lead source donut */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Lead Source Breakdown</h3>
          <div className="flex items-center gap-6">
            <ResponsiveContainer width={180} height={180} minWidth={0}>
              <PieChart>
                <Pie data={sourceData} cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                  paddingAngle={3} dataKey="value">
                  {sourceData.map((e, i) => <Cell key={i} fill={e.color} stroke="none" />)}
                </Pie>
                <Tooltip {...tt} formatter={v => [`${v}%`, '']} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {sourceData.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                  <span className="text-xs text-gray-500">{d.name}</span>
                  <span className="text-xs font-semibold text-gray-900 ml-auto pl-4">{d.value}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

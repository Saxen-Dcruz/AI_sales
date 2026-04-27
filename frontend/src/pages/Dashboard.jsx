import { motion } from 'framer-motion'
import AnalyticsCard from '../components/cards/AnalyticsCard'
import {
  Target, Phone, Linkedin, PhoneIncoming, PhoneOutgoing,
  TrendingUp, DollarSign, Star
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line
} from 'recharts'

const cards = [
  { title: 'Total Leads', value: '24,381', change: 12.4, changeLabel: 'vs last month', icon: Target, color: 'blue', data: [12,18,14,22,19,28,24,32,29,38] },
  { title: 'Active AI Calls', value: '142', change: 8.1, changeLabel: 'right now', icon: Phone, color: 'green', data: [80,95,110,102,130,118,140,135,142,148] },
  { title: 'LinkedIn Leads', value: '8,204', change: 23.5, changeLabel: 'vs last month', icon: Linkedin, color: 'cyan', data: [30,45,52,48,60,72,68,80,75,90] },
  { title: 'Inbound Calls', value: '3,920', change: 5.2, changeLabel: 'vs last week', icon: PhoneIncoming, color: 'purple', data: [200,210,240,220,260,250,280,265,300,290] },
  { title: 'Outbound Calls', value: '11,248', change: -2.3, changeLabel: 'vs last week', icon: PhoneOutgoing, color: 'orange', data: [500,480,520,490,510,490,505,480,498,490] },
  { title: 'Conversion Rate', value: '18.4', suffix: '%', change: 3.7, changeLabel: 'vs last month', icon: TrendingUp, color: 'pink', data: [12,13,14,13,15,16,15,17,17,18] },
  { title: 'Revenue from Leads', value: '284,500', prefix: '$', change: 18.2, changeLabel: 'vs last month', icon: DollarSign, color: 'green', data: [100,120,140,130,155,170,160,190,205,220] },
  { title: 'Qualified Leads', value: '4,491', change: 9.8, changeLabel: 'vs last month', icon: Star, color: 'red', data: [150,180,170,200,210,225,215,240,250,265] },
]

const revenueData = [
  { month: 'Jan', revenue: 42000, leads: 1200, calls: 3400 },
  { month: 'Feb', revenue: 58000, leads: 1450, calls: 3800 },
  { month: 'Mar', revenue: 52000, leads: 1300, calls: 3600 },
  { month: 'Apr', revenue: 71000, leads: 1800, calls: 4200 },
  { month: 'May', revenue: 66000, leads: 1650, calls: 4000 },
  { month: 'Jun', revenue: 85000, leads: 2100, calls: 4800 },
  { month: 'Jul', revenue: 79000, leads: 2000, calls: 4600 },
  { month: 'Aug', revenue: 95000, leads: 2400, calls: 5200 },
  { month: 'Sep', revenue: 88000, leads: 2200, calls: 5000 },
  { month: 'Oct', revenue: 110000, leads: 2800, calls: 5600 },
  { month: 'Nov', revenue: 102000, leads: 2600, calls: 5400 },
  { month: 'Dec', revenue: 128000, leads: 3100, calls: 6200 },
]

const tooltipStyle = {
  contentStyle: { background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', color: '#111827', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}

const pageVariants = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, staggerChildren: 0.06 } },
}

export default function Dashboard() {
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

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Revenue area chart */}
        <div className="lg:col-span-2 glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Revenue Overview</h3>
              <p className="text-xs text-gray-500 mt-0.5">Monthly revenue trend</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge badge-green">+18.2%</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <AreaChart data={revenueData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6172f3" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6172f3" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="leadsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" />
              <XAxis dataKey="month" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip {...tooltipStyle} formatter={(v, n) => [n === 'revenue' ? `$${v.toLocaleString()}` : v, n === 'revenue' ? 'Revenue' : 'Leads']} />
              <Area type="monotone" dataKey="revenue" stroke="#6172f3" strokeWidth={2} fill="url(#revGrad)" dot={false} />
              <Area type="monotone" dataKey="leads" stroke="#10b981" strokeWidth={2} fill="url(#leadsGrad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Calls bar chart */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Call Volume</h3>
              <p className="text-xs text-gray-500 mt-0.5">Monthly outbound</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220} minWidth={0}>
            <BarChart data={revenueData.slice(-6)} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={18}>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#5e5f6e', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...tooltipStyle} />
              <Bar dataKey="calls" radius={[6, 6, 0, 0]}>
                {revenueData.slice(-6).map((_, i) => (
                  <rect key={i} fill={`hsl(${240 + i * 15}, 70%, 60%)`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Recent activity */}
        <div className="lg:col-span-2 glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-3">
            {[
              { event: 'New lead qualified', name: 'Sarah Mitchell – TechCorp', time: '2m ago', badge: 'badge-green', badgeText: 'Qualified' },
              { event: 'AI call completed', name: 'John Davis – InnovateTech', time: '8m ago', badge: 'badge-blue', badgeText: 'AI Call' },
              { event: 'LinkedIn lead scraped', name: 'Emily Chen – StartupX', time: '14m ago', badge: 'badge-purple', badgeText: 'LinkedIn' },
              { event: 'Lead converted', name: 'Mike Torres – GlobalServ', time: '22m ago', badge: 'badge-green', badgeText: 'Converted' },
              { event: 'Inbound call received', name: 'Amy Park – FinanceAI', time: '31m ago', badge: 'badge-orange', badgeText: 'Inbound' },
            ].map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2.5 border-b border-gray-200 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-primary-600/20 flex items-center justify-center">
                    <div className="w-2 h-2 rounded-full bg-primary-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-900">{item.event}</p>
                    <p className="text-[11px] text-gray-500">{item.name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={item.badge}>{item.badgeText}</span>
                  <span className="text-[11px] text-gray-400">{item.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top metrics */}
        <div className="glass-card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Performance</h3>
          <div className="space-y-4">
            {[
              { label: 'Lead Quality Score', value: 87, color: '#6172f3' },
              { label: 'AI Call Success Rate', value: 73, color: '#10b981' },
              { label: 'LinkedIn Conversion', value: 42, color: '#06b6d4' },
              { label: 'Revenue Target', value: 91, color: '#8b5cf6' },
              { label: 'Response Time SLA', value: 96, color: '#f59e0b' },
            ].map((m, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs text-gray-500">{m.label}</span>
                  <span className="text-xs font-bold text-gray-900">{m.value}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: m.color, boxShadow: `0 0 8px ${m.color}60` }}
                    initial={{ width: 0 }}
                    animate={{ width: `${m.value}%` }}
                    transition={{ delay: 0.3 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
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

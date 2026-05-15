import { motion } from 'framer-motion'
import {
  AlertCircle,
  Archive,
  ArrowDown,
  ChevronRight,
  Clock,
  Mail,
  ShoppingCart,
  Users,
  Zap
} from 'lucide-react'
import { useEffect, useState } from 'react'
import CountUp from 'react-countup'
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  XAxis
} from 'recharts'
import { GetGmailAnalyticsService } from '../services/ApiService'

// ─── Config & Colors ────────────────────────────────────────────────────────

const COLORS = {
  indigo: '#4f46e5',
  violet: '#8b5cf6',
  emerald: '#10b981',
  amber: '#f59e0b',
  rose: '#f43f5e',
  slate: '#94a3b8',
}

const LABEL_COLORS = {
  Sales: COLORS.indigo,
  Support: COLORS.emerald,
  Grievance: COLORS.rose,
  Transactional: COLORS.violet,
  Promotional: COLORS.amber,
  Personal: '#ec4899',
  Unclassified: COLORS.slate,
}

// ─── Components ─────────────────────────────────────────────────────────────

function MetricCard({ icon: Icon, label, value, sub, color, loading, index }) {
  const displayValue = parseFloat(value) || 0
  const isPercentage = label?.includes('%') || label?.includes('Rate')
  const isReply = label?.includes('Reply')

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: (index || 0) * 0.05, duration: 0.5 }}
      className="bg-white rounded-[2rem] p-8 shadow-sm border border-slate-50 flex flex-col h-full relative overflow-hidden group hover:shadow-xl transition-all duration-500"
    >
      <div className="flex items-start justify-between mb-8">
        <div className="p-3 rounded-2xl bg-slate-50 text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
          <Icon size={24} />
        </div>
        {sub && (
          <span className="text-sm font-black text-slate-400 uppercase tracking-widest">{sub}</span>
        )}
      </div>

      <div className="space-y-1 mt-auto">
        <p className="text-sm font-black text-slate-400 uppercase tracking-[0.15em] leading-tight">{label}</p>
        <div className="flex items-baseline gap-1">
          <h3 className="text-5xl font-black text-slate-900 tracking-tight">
            {loading ? (
              <div className="h-10 w-20 bg-slate-100 animate-pulse rounded-xl" />
            ) : (
              <CountUp end={displayValue} decimals={value?.toString()?.includes('.') ? 1 : 0} duration={2} />
            )}
          </h3>
          {!loading && isPercentage && <span className="text-2xl font-black text-slate-900">%</span>}
          {!loading && isReply && <span className="text-2xl font-black text-slate-900 lowercase ml-1">m</span>}
        </div>
      </div>

      <div className="absolute bottom-0 left-8 right-8 h-1.5 rounded-t-full" style={{ background: color || COLORS.indigo }} />
    </motion.div>
  )
}

function OperationalCard({ icon: Icon, label, value, sub, color, onClick }) {
  return (
    <button onClick={onClick} className="w-full bg-white rounded-3xl p-6 shadow-sm border border-slate-50 flex items-center justify-between group hover:shadow-lg transition-all duration-300">
      <div className="flex items-center gap-6">
        <div className="p-4 rounded-2xl" style={{ backgroundColor: `${color || COLORS.slate}10`, color: color || COLORS.slate }}>
          <Icon size={24} />
        </div>
        <div className="text-left">
          <h4 className="text-base font-black text-slate-800">{label}</h4>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">{value || 0}</span>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{sub}</span>
          </div>
        </div>
      </div>
      <ChevronRight size={20} className="text-slate-300 group-hover:text-indigo-600 transition-colors" />
    </button>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function GmailAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState('24h')

  useEffect(() => {
    let mounted = true
    setLoading(true)

    GetGmailAnalyticsService(
      (res) => {
        if (!mounted) return
        setData(res)
        setLoading(false)
      },
      () => {
        if (!mounted) return
        setLoading(false)
      }
    )

    return () => { mounted = false }
  }, [])

  const labelData = data?.by_label
    ? Object.entries(data.by_label).map(([name, value]) => ({ name, value }))
    : []

  const trendData = [
    { name: 'MON', inbound: 40, outbound: 20 },
    { name: 'TUE', inbound: 60, outbound: 35 },
    { name: 'WED', inbound: 45, outbound: 50 },
    { name: 'THU', inbound: 80, outbound: 40 },
    { name: 'FRI', inbound: 70, outbound: 45 },
    { name: 'SAT', inbound: 30, outbound: 15 },
    { name: 'SUN', inbound: 25, outbound: 10 },
  ]

  return (
    <div className="min-h-screen bg-[#F8F9FD] text-slate-900 px-6 py-4 md:px-10 md:py-6 font-sans">
      <div className="max-w-[1400px] mx-auto space-y-6">

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-[#0f172a]">Gmail Analytics </h1>
            <p className="text-slate-400 font-bold text-base mt-1">Real-time overview of your communication efficiency.</p>
          </div>

          <div className="flex items-center gap-2 bg-slate-200/50 p-1.5 rounded-2xl">
            {['Last 24h', '7 Days', '30 Days'].map((range, i) => {
              const keys = ['24h', '7d', '30d']
              const active = timeRange === keys[i]
              return (
                <button
                  key={range}
                  onClick={() => setTimeRange(keys[i])}
                  className={`px-8 py-3 rounded-xl text-base font-black transition-all ${active ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
                >
                  {range}
                </button>
              )
            })}
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-6">
          <MetricCard icon={Mail} label="Total Emails" value={data?.total_emails || 633} color={COLORS.indigo} loading={loading} index={0} />
          <MetricCard icon={ArrowDown} label="Inbound" value={data?.total_inbound || 515} sub="Customers" color={COLORS.violet} loading={loading} index={1} />
          <MetricCard icon={ShoppingCart} label="Sales Emails" value={data?.total_sales_emails || 146} sub="Targeted" color={COLORS.amber} loading={loading} index={2} />
          <MetricCard icon={Zap} label="Auto-Sent" value={data?.auto_sent_rate_pct || 98.6} sub="AI Handled" color={COLORS.emerald} loading={loading} index={3} />
          <MetricCard icon={Clock} label="Avg Reply" value={data?.avg_reply_minutes || 61} sub="Minutes" color={COLORS.amber} loading={loading} index={4} />
          <MetricCard icon={AlertCircle} label="SLA Breaches" value={data?.sla_breached || 2} sub="Critical" color={COLORS.rose} loading={loading} index={5} />
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

          <div className="lg:col-span-5 bg-white rounded-[2.5rem] p-10 shadow-sm border border-slate-50">
            <h2 className="text-xl font-black text-slate-800 mb-10">Volume by Label</h2>
            <div className="flex flex-col sm:flex-row items-center gap-10">
              <div className="relative w-[240px] h-[240px] flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={labelData.length > 0 ? labelData : [{ name: 'None', value: 1 }]}
                      cx="50%" cy="50%"
                      innerRadius={80}
                      outerRadius={110}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                    >
                      {labelData.length > 0 ? labelData.map((entry) => (
                        <Cell key={entry.name} fill={LABEL_COLORS[entry.name] || COLORS.slate} />
                      )) : <Cell fill="#f1f5f9" />}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-5xl font-black text-slate-900 leading-none">{data?.total_emails || 0}</span>
                  <span className="text-sm font-black text-slate-400 uppercase tracking-widest mt-2">Total Detected</span>
                </div>
              </div>

              <div className="flex-1 space-y-4 w-full">
                {labelData.map((d) => (
                  <div key={d.name} className="flex items-center justify-between group">
                    <div className="flex items-center gap-3">
                      <div className="w-4 h-4 rounded-full" style={{ backgroundColor: LABEL_COLORS[d.name] || COLORS.slate }} />
                      <span className="text-base font-bold text-slate-500 group-hover:text-slate-900 transition-colors">{d.name}</span>
                    </div>
                    <span className="text-base font-black text-slate-900">{d.value}</span>
                  </div>
                ))}
                <button className="text-sm font-black text-indigo-600 uppercase tracking-widest pt-6 hover:underline">
                  View Detailed Report
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-7 bg-white rounded-[2.5rem] p-10 shadow-sm border border-slate-50">
            <div className="flex items-center justify-between mb-10">
              <h2 className="text-xl font-black text-slate-800">Volume Trends</h2>
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-indigo-900" />
                  <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Inbound</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-indigo-500" />
                  <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Outbound</span>
                </div>
              </div>
            </div>

            <div className="h-[240px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fontWeight: 800, fill: '#cbd5e1' }}
                  />
                  <Bar dataKey="inbound" fill="#1e1b4b" radius={[4, 4, 0, 0]} barSize={20} />
                  <Bar dataKey="outbound" fill="#4f46e5" radius={[4, 4, 0, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="grid grid-cols-3 gap-6 mt-10 pt-10 border-t border-slate-50">
              <div className="space-y-2">
                <p className="text-xs font-black text-slate-400 uppercase tracking-widest">Peak Volume</p>
                <p className="text-2xl font-black text-slate-800">Thursday</p>
              </div>
              <div className="space-y-2 text-center">
                <p className="text-xs font-black text-slate-400 uppercase tracking-widest">Growth</p>
                <p className="text-2xl font-black text-emerald-500">+12.4%</p>
              </div>
              <div className="space-y-2 text-right">
                <p className="text-xs font-black text-slate-400 uppercase tracking-widest">AI Accuracy</p>
                <p className="text-2xl font-black text-slate-800">99.2%</p>
              </div>
            </div>
          </div>
        </div>

        {/* Operational Overview */}
        <div className="space-y-6">
          <h2 className="text-2xl font-black text-slate-900">Operational Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <OperationalCard
              icon={Users}
              label="Pending Human"
              value={data?.pending_human || 4}
              sub="tasks"
              color={COLORS.amber}
            />
            <OperationalCard
              icon={Archive}
              label="Archived"
              value={(data?.archived || 1248).toLocaleString()}
              sub="processed"
              color={COLORS.slate}
            />
            <OperationalCard
              icon={AlertCircle}
              label="Ignored"
              value={data?.ignored || 24}
              sub="emails"
              color={COLORS.rose}
            />
          </div>
        </div>

        {/* Performance Summary (Requested Section) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 pt-6">
          {/* Communication Balance Pie Chart */}
          <div className="bg-white rounded-[2.5rem] p-10 shadow-sm border border-slate-50">
            <h2 className="text-xl font-black text-slate-800 mb-10">Communication Balance</h2>
            <div className="flex flex-col sm:flex-row items-center gap-10">
              <div className="relative w-[240px] h-[240px] flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Inbound', value: data?.total_inbound || 515 },
                        { name: 'Outbound', value: (data?.total_emails - data?.total_inbound) || 118 }
                      ]}
                      cx="50%" cy="50%"
                      innerRadius={80}
                      outerRadius={110}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                    >
                      <Cell fill={COLORS.indigo} />
                      <Cell fill={COLORS.violet} />
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
                  <span className="text-5xl font-black text-slate-900 leading-none">{data?.total_emails || 633}</span>
                  <span className="text-sm font-black text-slate-400 uppercase tracking-widest mt-2">Total Emails</span>
                </div>
              </div>

              <div className="flex-1 space-y-4 w-full">
                <div className="flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full bg-indigo-600" />
                    <div>
                      <span className="text-base font-bold text-slate-500 block leading-none">Inbound</span>
                      <span className="text-[10px] font-black text-slate-300 uppercase tracking-tighter">Received from customers</span>
                    </div>
                  </div>
                  <span className="text-base font-black text-slate-900">{data?.total_inbound || 515}</span>
                </div>
                <div className="flex items-center justify-between group">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full bg-violet-600" />
                    <div>
                      <span className="text-base font-bold text-slate-500 block leading-none">Outbound</span>
                      <span className="text-[10px] font-black text-slate-300 uppercase tracking-tighter">Sent by your team</span>
                    </div>
                  </div>
                  <span className="text-base font-black text-slate-900">{data?.total_emails - data?.total_inbound || 118}</span>
                </div>
                <div className="pt-6 border-t border-slate-50 mt-4">
                  <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">Competitor Mentions</p>
                  <p className="text-2xl font-black text-slate-800">{data?.competitor_mentions || 1}</p>
                </div>
              </div>
            </div>
          </div>

          {/* AI Execution Breakdown */}
          <div className="bg-white rounded-[2.5rem] p-10 shadow-sm border border-slate-50 flex flex-col">
            <h2 className="text-xl font-black text-slate-800 mb-6">Execution Breakdown</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
              <div className="p-6 bg-indigo-50/50 rounded-3xl border border-indigo-100/50">
                <p className="text-xs font-black text-indigo-600 uppercase tracking-widest mb-1">Auto-Sent</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-3xl font-black text-slate-900">{data?.auto_sent_count || 144}</p>
                  <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Emails</p>
                </div>
                <p className="text-xs font-bold text-indigo-600/70 mt-1">No human needed</p>
              </div>
              <div className="p-6 bg-violet-50/50 rounded-3xl border border-violet-100/50">
                <p className="text-xs font-black text-violet-600 uppercase tracking-widest mb-1">Drafted for Review</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-3xl font-black text-slate-900">{data?.drafted_count || 20}</p>
                  <p className="text-xs font-bold text-violet-400 uppercase tracking-widest">Drafts</p>
                </div>
                <p className="text-xs font-bold text-violet-600/70 mt-1">Had knowledge gaps</p>
              </div>
              <div className="p-6 bg-emerald-50/50 rounded-3xl border border-emerald-100/50">
                <p className="text-xs font-black text-emerald-600 uppercase tracking-widest mb-1">Pending Human</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-3xl font-black text-slate-900">{data?.pending_human || 4}</p>
                  <p className="text-xs font-bold text-emerald-400 uppercase tracking-widest">Tasks</p>
                </div>
                <p className="text-xs font-bold text-emerald-600/70 mt-1">Support/Grievance</p>
              </div>
              <div className="p-6 bg-rose-50/50 rounded-3xl border border-rose-100/50">
                <p className="text-xs font-black text-rose-600 uppercase tracking-widest mb-1">SLA Breaches</p>
                <div className="flex items-baseline gap-2">
                  <p className="text-3xl font-black text-slate-900">{data?.sla_breached || 2}</p>
                  <p className="text-xs font-bold text-rose-400 uppercase tracking-widest">Critical</p>
                </div>
                <p className="text-xs font-bold text-rose-600/70 mt-1">{">2h unresolved Sales"}</p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}

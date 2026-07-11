import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Mic, Radio, ThumbsUp, AlertCircle, Clock, HelpCircle,
  Phone,
  CheckCircle,
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Cell, PieChart, Pie, Legend, LineChart, Line,
} from 'recharts'
import { GetVoiceAnalyticsService, GetCallIntelligenceService } from '../services/ApiService'

const tooltipStyle = {
  contentStyle: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', fontSize: '12px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' },
  cursor: { fill: 'rgba(0,0,0,0.04)' },
}
const CHANNEL_COLORS   = { whatsapp: '#10b981', gmail: '#6172f3', direct: '#f97316' }
const INTENT_COLORS    = { ready_to_buy: '#10b981', exploring: '#6172f3', not_interested: '#ef4444', unknown: '#94a3b8' }
const SENTIMENT_COLORS = { POSITIVE: '#10b981', NEUTRAL: '#6172f3', FRUSTRATED: '#ef4444' }
const FUNNEL_COLORS    = ['#6172f3', '#8b5cf6', '#f59e0b', '#10b981', '#059669']

function fmt(n, prefix = '') {
  if (n === null || n === undefined) return '—'
  if (n >= 1_000_000) return `${prefix}${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${prefix}${(n / 1_000).toFixed(1)}K`
  return `${prefix}${Number(n).toLocaleString()}`
}

function KpiCard({ icon: Icon, label, value, sub, color, pulse }) {
  const map = {
    purple: { bg: 'bg-purple-50', text: 'text-purple-600', ring: 'ring-purple-100' },
    green:  { bg: 'bg-emerald-50', text: 'text-emerald-600', ring: 'ring-emerald-100' },
    amber:  { bg: 'bg-amber-50', text: 'text-amber-600', ring: 'ring-amber-100' },
    rose:   { bg: 'bg-rose-50', text: 'text-rose-600', ring: 'ring-rose-100' },
    blue:   { bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-100' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', ring: 'ring-orange-100' },
  }
  const c = map[color] || map.purple
  return (
    <div className="glass-card p-4 flex items-center gap-3 relative overflow-hidden">
      {pulse && (
        <span className="absolute top-2 right-2 flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
      )}
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${c.bg} ring-1 ${c.ring}`}>
        <Icon size={16} className={c.text} />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
        <p className="text-lg font-bold text-gray-900 leading-tight">{value}</p>
        {sub && <p className="text-[10px] text-gray-400">{sub}</p>}
      </div>
    </div>
  )
}

function Section({ title, sub, children }) {
  return (
    <div className="glass-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
      {children}
    </div>
  )
}

function FunnelBar({ label, value, pct, color, sub }) {
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-700">{label}</span>
        <div className="flex items-center gap-2">
          {sub && <span className="text-[10px] text-gray-400">{sub}</span>}
          <span className="text-xs font-bold text-gray-900">{fmt(value)}</span>
        </div>
      </div>
      <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
        <motion.div className="h-full rounded-full" style={{ background: color }}
          initial={{ width: 0 }} animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }} />
      </div>
    </div>
  )
}

export default function VoiceAnalytics() {
  const [voice, setVoice] = useState(null)
  const [intel, setIntel] = useState(null)
  const [days, setDays]   = useState(30)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      new Promise(r => GetVoiceAnalyticsService(r, () => r(null))),
      new Promise(r => GetCallIntelligenceService(days, r, () => r(null))),
    ]).then(([v, i]) => { setVoice(v); setIntel(i); setLoading(false) })
  }, [days])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-gray-400">
          <Mic size={20} className="animate-pulse text-purple-500" />
          <span className="text-sm">Loading voice intelligence…</span>
        </div>
      </div>
    )
  }

  // ── derived ────────────────────────────────────────────────────────────────
  const vq   = voice ?? {}
  const cf   = intel?.call_funnel ?? {}
  const vp   = intel?.voice_vs_phone ?? {}
  const qi   = intel?.voice_quality ?? {}

  const funnelSteps = [
    { label: 'Total calls received', value: cf.total_calls, pct: 100, color: FUNNEL_COLORS[0] },
    { label: 'Calls with transcript', value: cf.with_transcript, pct: cf.total_calls ? cf.with_transcript / cf.total_calls * 100 : 0, sub: `${cf.transcript_rate ?? 0}%`, color: FUNNEL_COLORS[1] },
    { label: 'Intent classified', value: cf.intent_classified, pct: cf.total_calls ? cf.intent_classified / cf.total_calls * 100 : 0, color: FUNNEL_COLORS[2] },
    { label: 'Ready to buy', value: cf.ready_to_buy, pct: cf.total_calls ? cf.ready_to_buy / cf.total_calls * 100 : 0, sub: `${cf.rtb_rate ?? 0}% of classified`, color: FUNNEL_COLORS[3] },
    { label: 'Closed deals', value: cf.closed_deal, pct: cf.total_calls ? cf.closed_deal / cf.total_calls * 100 : 0, sub: `${cf.close_rate ?? 0}% close rate`, color: FUNNEL_COLORS[4] },
  ]

  const channelBreakdown = Object.entries(vq.channel_breakdown ?? {}).map(([ch, n]) => ({
    name: ch, value: n, fill: CHANNEL_COLORS[ch] ?? '#94a3b8',
  }))

  const intentTrend = (intel?.intent_trend ?? []).map(w => ({ ...w }))
  const sentimentTrend = (intel?.sentiment_trend ?? []).map(w => ({ ...w }))
  const csatTrend = (intel?.csat_trend ?? []).map(w => ({ ...w }))

  const topProducts = (intel?.top_products ?? []).slice(0, 8)
  const topGaps     = (intel?.top_gaps ?? []).slice(0, 6)
  const chConv      = intel?.channel_conversion ?? {}
  const escAnalysis = intel?.escalation_analysis ?? {}
  const kbCoverage  = (intel?.knowledge_coverage ?? []).slice(0, 6)

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="space-y-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
            <Mic size={20} className="text-purple-600" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">Voice Bridge Analytics</h1>
            <p className="text-xs text-gray-400">AI voice calls · Escalation · Feedback · Knowledge gaps</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                days === d ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* ── Voice KPI strip ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard icon={Radio}        label="Active Now"       value={fmt(vq.total_sessions ? (vq.total_sessions - vq.completed - vq.escalated - vq.expired) : voice?.active_now ?? 0)} sub="live voice sessions"   color="purple" pulse={(voice?.active_now ?? 0) > 0} />
        <KpiCard icon={CheckCircle}  label="Completed"        value={fmt(vq.completed)}                    sub={`${days}d window`}          color="green" />
        <KpiCard icon={ThumbsUp}     label="CSAT Score"       value={vq.avg_feedback_score !== null && vq.avg_feedback_score !== undefined ? `${vq.avg_feedback_score}/5` : '—'} sub="avg post-call rating" color="green" />
        <KpiCard icon={AlertCircle}  label="Escalation Rate"  value={vq.escalation_rate !== null && vq.escalation_rate !== undefined ? `${vq.escalation_rate}%` : '—'} sub="of completed calls"   color="amber" />
        <KpiCard icon={Clock}        label="Avg Duration"     value={qi.avg_duration_seconds ? `${Math.round(qi.avg_duration_seconds)}s` : '—'} sub="per session"    color="blue" />
        <KpiCard icon={HelpCircle}   label="Avg Gaps/Call"    value={qi.avg_unanswered !== null && qi.avg_unanswered !== undefined ? Number(qi.avg_unanswered).toFixed(1) : '—'} sub="unanswered questions" color="rose" />
      </div>

      {/* ── Row 1: Call funnel + Channel breakdown ───────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Call funnel */}
        <div className="lg:col-span-2">
          <Section title="Call Conversion Funnel" sub={`Last ${days} days — voice + phone calls`}>
            {funnelSteps.map((s, i) => (
              <FunnelBar key={i} {...s} />
            ))}
            <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-[10px] text-gray-400">Transcript rate</p>
                <p className="text-sm font-bold text-purple-600">{cf.transcript_rate ?? 0}%</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">RTB rate</p>
                <p className="text-sm font-bold text-amber-600">{cf.rtb_rate ?? 0}%</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">Close rate</p>
                <p className="text-sm font-bold text-emerald-600">{cf.close_rate ?? 0}%</p>
              </div>
            </div>
          </Section>
        </div>

        {/* Channel breakdown */}
        <Section title="Voice Session Channels" sub="Where calls originate">
          {channelBreakdown.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160} minWidth={0}>
                <PieChart>
                  <Pie data={channelBreakdown} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60} paddingAngle={4}>
                    {channelBreakdown.map(e => <Cell key={e.name} fill={e.fill} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-3 space-y-2">
                {channelBreakdown.map(ch => (
                  <div key={ch.name} className="flex items-center justify-between p-2 rounded-lg" style={{ background: `${ch.fill}14` }}>
                    <span className="text-[10px] font-semibold capitalize" style={{ color: ch.fill }}>{ch.name}</span>
                    <span className="text-xs font-bold text-gray-900">{ch.value} sessions</span>
                  </div>
                ))}
              </div>
            </>
          ) : <p className="text-xs text-gray-400 py-8 text-center">No voice sessions yet.</p>}
        </Section>
      </div>

      {/* ── Row 2: Voice vs Phone + Escalation ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Voice vs phone comparison */}
        <Section title="Voice Bridge vs Phone Calls" sub="Intent quality + conversion comparison">
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: 'Voice Bridge', data: vp.voice, color: '#8b5cf6', icon: Mic },
              { label: 'Phone Calls',  data: vp.phone, color: '#f97316', icon: Phone },
            ].map(({ label, data, color, icon: Icon }) => (
              <div key={label} className="rounded-xl p-4 border" style={{ borderColor: `${color}30`, background: `${color}08` }}>
                <div className="flex items-center gap-2 mb-3">
                  <Icon size={13} style={{ color }} />
                  <span className="text-xs font-semibold" style={{ color }}>{label}</span>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-[10px] text-gray-500">Volume</span>
                    <span className="text-[10px] font-bold text-gray-900">{fmt(data?.count ?? data?.sessions)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[10px] text-gray-500">RTB rate</span>
                    <span className="text-[10px] font-bold text-emerald-600">{data?.rtb_rate ?? 0}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[10px] text-gray-500">Avg duration</span>
                    <span className="text-[10px] font-bold text-gray-900">{data?.avg_duration ? `${Math.round(data.avg_duration)}s` : '—'}</span>
                  </div>
                  {data?.escalation_rate !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-[10px] text-gray-500">Escalation</span>
                      <span className="text-[10px] font-bold text-amber-600">{data.escalation_rate}%</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Escalation analysis */}
        <Section title="Escalation Analysis" sub="When and why calls hand off to humans">
          <div className="grid grid-cols-2 gap-3 mb-4">
            {[
              { label: 'Total escalations', value: fmt(escAnalysis.total), color: 'text-amber-600' },
              { label: 'To Google Meet', value: fmt(escAnalysis.to_gmeet), color: 'text-blue-600' },
              { label: 'To office call', value: fmt(escAnalysis.to_office_call), color: 'text-orange-600' },
              { label: 'Escalation rate', value: `${escAnalysis.escalation_rate ?? 0}%`, color: 'text-rose-600' },
            ].map(s => (
              <div key={s.label} className="bg-gray-50 rounded-xl p-3 text-center">
                <p className="text-[10px] text-gray-400">{s.label}</p>
                <p className={`text-base font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl bg-amber-50 border border-amber-100 p-3 text-center">
            <p className="text-[10px] text-amber-600 font-medium">Avg questions before escalation</p>
            <p className="text-2xl font-bold text-amber-700 mt-1">
              {escAnalysis.avg_questions_before_esc !== null && escAnalysis.avg_questions_before_esc !== undefined
                ? Number(escAnalysis.avg_questions_before_esc).toFixed(1)
                : '—'}
            </p>
            <p className="text-[10px] text-amber-500 mt-0.5">unanswered before handoff</p>
          </div>
        </Section>
      </div>

      {/* ── Row 3: Intent trend + Sentiment trend ───────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Intent Trend" sub="Weekly buying signals across all calls">
          {intentTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200} minWidth={0}>
              <BarChart data={intentTrend} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,0.05)" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#5e5f6e', fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
                <Bar dataKey="ready_to_buy" stackId="a" fill={INTENT_COLORS.ready_to_buy} name="Ready to Buy" radius={[0,0,0,0]} />
                <Bar dataKey="exploring"    stackId="a" fill={INTENT_COLORS.exploring}    name="Exploring" />
                <Bar dataKey="not_interested" stackId="a" fill={INTENT_COLORS.not_interested} name="Not Interested" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-gray-400 py-8 text-center">No intent data yet — need transcribed calls.</p>}
        </Section>

        <Section title="Sentiment Trend" sub="Customer mood per week">
          {sentimentTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={200} minWidth={0}>
              <LineChart data={sentimentTrend} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="rgba(0,0,0,0.05)" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: '#5e5f6e', fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip {...tooltipStyle} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
                <Line type="monotone" dataKey="POSITIVE"   stroke={SENTIMENT_COLORS.POSITIVE}   strokeWidth={2} dot={false} name="Positive" />
                <Line type="monotone" dataKey="NEUTRAL"    stroke={SENTIMENT_COLORS.NEUTRAL}    strokeWidth={2} dot={false} name="Neutral" />
                <Line type="monotone" dataKey="FRUSTRATED" stroke={SENTIMENT_COLORS.FRUSTRATED} strokeWidth={2} dot={false} name="Frustrated" />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="text-xs text-gray-400 py-8 text-center">No sentiment data yet.</p>}
        </Section>
      </div>

      {/* ── Row 4: Top products + Top gaps ──────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Top Products from Calls" sub="Most mentioned in transcripts + RTB rate">
          {topProducts.length > 0 ? (
            <div className="space-y-3">
              {topProducts.map((p, i) => (
                <div key={p.product}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[10px] text-gray-400 w-4 flex-shrink-0">{i + 1}</span>
                      <span className="text-xs font-medium text-gray-800 truncate">{p.product}</span>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-[10px] text-emerald-600 font-semibold">{p.rtb_rate}% RTB</span>
                      <span className="text-xs font-bold text-gray-900 w-6 text-right">{p.mentions}</span>
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                    <motion.div className="h-full rounded-full bg-purple-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.round(p.mentions / topProducts[0].mentions * 100)}%` }}
                      transition={{ delay: i * 0.08, duration: 0.7, ease: 'easeOut' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-gray-400 py-8 text-center">No product mentions yet — need transcribed calls.</p>}
        </Section>

        <Section title="Top Knowledge Gaps" sub="Questions AI couldn't answer (from voice + calls)">
          {topGaps.length > 0 ? (
            <div className="space-y-2">
              {topGaps.map((g, i) => (
                <div key={i} className={`p-3 rounded-xl border ${g.resolved ? 'border-emerald-100 bg-emerald-50/40' : 'border-rose-100 bg-rose-50/40'}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs text-gray-800 flex-1 leading-relaxed">{g.question}</p>
                    <div className="text-right flex-shrink-0">
                      <span className={`text-[10px] font-bold ${g.resolved ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {g.resolved ? '✓ resolved' : `${g.occurrences}× asked`}
                      </span>
                    </div>
                  </div>
                  {g.topics?.length > 0 && (
                    <div className="mt-1 flex gap-1 flex-wrap">
                      {g.topics.map(t => (
                        <span key={t} className="text-[9px] bg-white/60 px-1.5 py-0.5 rounded text-gray-500">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-gray-400 py-8 text-center">No knowledge gaps captured yet.</p>}
        </Section>
      </div>

      {/* ── Row 5: Channel conversion + CSAT trend ──────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Channel conversion */}
        <Section title="Channel → Deal Conversion" sub="Which channel drives most closed deals">
          <div className="space-y-4">
            {Object.entries(chConv).map(([ch, data]) => {
              const color = CHANNEL_COLORS[ch] ?? '#94a3b8'
              return (
                <div key={ch}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
                      <span className="text-xs font-semibold capitalize text-gray-700">{ch}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-[10px] text-gray-400">{data.leads} leads</span>
                      <span className="text-[10px] text-gray-400">{data.closed_deals} deals</span>
                      <span className="text-xs font-bold" style={{ color }}>{data.conversion_rate}%</span>
                    </div>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                    <motion.div className="h-full rounded-full" style={{ background: color }}
                      initial={{ width: 0 }} animate={{ width: `${data.conversion_rate}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }} />
                  </div>
                </div>
              )
            })}
          </div>
        </Section>

        {/* CSAT trend */}
        <Section title="Customer Satisfaction Trend" sub="Weekly avg CSAT rating from post-call feedback">
          {csatTrend.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160} minWidth={0}>
                <LineChart data={csatTrend} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="rgba(0,0,0,0.05)" strokeDasharray="4 4" vertical={false} />
                  <XAxis dataKey="week" tick={{ fill: '#5e5f6e', fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[1, 5]} tick={{ fill: '#5e5f6e', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip {...tooltipStyle} formatter={(v) => [Number(v).toFixed(1), 'Avg CSAT']} />
                  <Line type="monotone" dataKey="avg_rating" stroke="#8b5cf6" strokeWidth={2.5} dot={{ fill: '#8b5cf6', r: 3 }} name="Avg Rating" />
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-3 flex items-center justify-between text-center">
                {[1, 2, 3, 4, 5].map(n => {
                  const inRange = csatTrend.some(w => Math.round(w.avg_rating) === n)
                  return (
                    <div key={n} className={`flex-1 ${inRange ? 'opacity-100' : 'opacity-30'}`}>
                      <p className="text-base">{'⭐'.repeat(n)}</p>
                      <p className="text-[9px] text-gray-400 mt-0.5">{n}</p>
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="py-8 text-center">
              <p className="text-xs text-gray-400">No feedback collected yet.</p>
              <p className="text-[10px] text-gray-300 mt-1">Feedback links sent automatically 5 min after each call.</p>
            </div>
          )}
        </Section>
      </div>

      {/* ── Row 6: Knowledge coverage by topic ──────────────────────────── */}
      {kbCoverage.length > 0 && (
        <Section title="Knowledge Base Coverage" sub="Gap resolution rate by topic — fill gaps to improve AI auto-replies">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {kbCoverage.map(k => {
              const pct = k.coverage_pct
              const color = pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444'
              return (
                <div key={k.topic} className="p-4 rounded-xl border border-gray-100 bg-gray-50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold capitalize text-gray-700">{k.topic}</span>
                    <span className="text-xs font-bold" style={{ color }}>{pct}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-200 overflow-hidden mb-2">
                    <motion.div className="h-full rounded-full" style={{ background: color }}
                      initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }} />
                  </div>
                  <div className="flex justify-between text-[10px] text-gray-400">
                    <span>{k.resolved} resolved</span>
                    <span>{k.unresolved} open</span>
                  </div>
                </div>
              )
            })}
          </div>
        </Section>
      )}
    </motion.div>
  )
}

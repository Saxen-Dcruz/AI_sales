import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Linkedin, UserPlus, Send, CheckCircle, MessageSquare,
  RefreshCw, Filter, ChevronDown, Search, Zap, Play,
  Building2, MapPin, Tag, X, Clock, Users,
} from 'lucide-react'
import {
  GetLinkedInOutreachService, GetLinkedInBudgetService,
  TriggerLinkedInDiscoveryService, QueueConnectionService,
  QueueMessageService, MarkConnectedService, MarkMessageSentService,
  MarkReplyReceivedService,
} from '../services/ApiService'

const LINKEDIN_BLUE = '#0077b5'

// ── Status configs ────────────────────────────────────────────────────────────

const CONN_STATUS = {
  not_sent:  { label: 'Not Sent',  bg: 'bg-gray-100 text-gray-500' },
  pending:   { label: 'Pending',   bg: 'bg-amber-100 text-amber-700' },
  connected: { label: 'Connected', bg: 'bg-emerald-100 text-emerald-700' },
  rejected:  { label: 'Rejected',  bg: 'bg-red-100 text-red-600' },
}

const MSG_STATUS = {
  not_sent: { label: 'Not Sent', bg: 'bg-gray-100 text-gray-400' },
  queued:   { label: 'Queued',   bg: 'bg-blue-100 text-blue-700' },
  sent:     { label: 'Sent',     bg: 'bg-indigo-100 text-indigo-700' },
  replied:  { label: 'Replied',  bg: 'bg-violet-100 text-violet-700' },
  bounced:  { label: 'Bounced',  bg: 'bg-red-100 text-red-600' },
}

// ── Reply modal ───────────────────────────────────────────────────────────────

function ReplyModal({ record, onClose, onSave }) {
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSave = () => {
    if (!text.trim()) return
    setSaving(true)
    MarkReplyReceivedService(record.id, text,
      () => { setSaving(false); onSave() },
      () => setSaving(false)
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-sm font-black text-gray-900">Record Reply from {record.full_name}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>
        </div>
        <div className="px-6 py-4 space-y-3">
          <p className="text-xs text-gray-400">Paste the reply preview (first 200 chars shown in CRM)</p>
          <textarea value={text} onChange={e => setText(e.target.value)} rows={4}
            placeholder="They said: I'd be happy to learn more about your data loggers…"
            className="w-full text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-xl p-3 resize-none focus:outline-none focus:border-indigo-400 focus:bg-white" />
        </div>
        <div className="px-6 pb-5 flex gap-3">
          <button onClick={onClose} className="flex-1 h-10 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={handleSave} disabled={saving || !text.trim()}
            className="flex-1 h-10 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-40 transition-all">
            {saving ? 'Saving…' : 'Save Reply'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ── Discovery modal ───────────────────────────────────────────────────────────

function DiscoveryModal({ onClose, onStarted }) {
  const [loading, setLoading] = useState(false)
  const [maxResults, setMaxResults] = useState(100)

  const handleStart = () => {
    setLoading(true)
    TriggerLinkedInDiscoveryService({ max_results_per_query: maxResults },
      () => { setLoading(false); onStarted() },
      () => setLoading(false)
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-sm font-black text-gray-900">Trigger Company Discovery</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <p className="text-xs font-semibold text-amber-800">Background Job</p>
            <p className="text-xs text-amber-700 mt-1">
              This searches across 200+ cities × 80+ industries for LinkedIn company URLs.
              It runs in the background — results appear automatically in your outreach pipeline.
            </p>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Max results per query</label>
            <input type="number" value={maxResults} onChange={e => setMaxResults(Number(e.target.value))}
              min={10} max={500}
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
          </div>
        </div>
        <div className="px-6 pb-5 flex gap-3">
          <button onClick={onClose} className="flex-1 h-10 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={handleStart} disabled={loading}
            className="flex-1 h-10 rounded-xl flex items-center justify-center gap-2 text-white text-sm font-bold hover:opacity-90 disabled:opacity-50 transition-all"
            style={{ background: LINKEDIN_BLUE }}>
            <Play size={14} />
            {loading ? 'Starting…' : 'Start Discovery'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ── Outreach row ──────────────────────────────────────────────────────────────

function OutreachRow({ record, onRefresh }) {
  const [busy, setBusy] = useState(null)
  const [replyOpen, setReplyOpen] = useState(false)

  const conn = CONN_STATUS[record.connection_status] || CONN_STATUS.not_sent
  const msg  = MSG_STATUS[record.message_status]    || MSG_STATUS.not_sent

  const act = (fn, key) => {
    setBusy(key)
    fn(record.id, () => { setBusy(null); onRefresh() }, () => setBusy(null))
  }

  return (
    <>
      <motion.div layout className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow p-4">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-black text-white"
            style={{ background: LINKEDIN_BLUE }}>
            {record.full_name?.[0] || 'L'}
          </div>

          <div className="flex-1 min-w-0">
            {/* Name + status badges */}
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <p className="text-sm font-black text-gray-900 truncate">{record.full_name || '—'}</p>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${conn.bg}`}>{conn.label}</span>
              {record.message_status !== 'not_sent' && (
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${msg.bg}`}>{msg.label}</span>
              )}
            </div>

            {/* Headline + meta */}
            {record.headline && <p className="text-xs text-gray-500 truncate mb-1">{record.headline}</p>}
            <div className="flex items-center gap-3 text-[11px] text-gray-400 flex-wrap mb-2">
              {record.company_name && <span className="flex items-center gap-1"><Building2 size={10} />{record.company_name}</span>}
              {record.location    && <span className="flex items-center gap-1"><MapPin size={10} />{record.location}</span>}
              {record.industry_tag && <span className="flex items-center gap-1"><Tag size={10} />{record.industry_tag}</span>}
              {record.role_category && <span className="flex items-center gap-1"><Users size={10} />{record.role_category}</span>}
            </div>

            {/* Reply preview */}
            {record.reply_preview && (
              <p className="text-xs text-violet-700 bg-violet-50 border border-violet-100 rounded-lg px-3 py-1.5 mb-2 line-clamp-1">
                Reply: {record.reply_preview}
              </p>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Queue connection */}
              {record.connection_status === 'not_sent' && (
                <button onClick={() => act(QueueConnectionService, 'conn')} disabled={busy === 'conn'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
                  style={{ background: `${LINKEDIN_BLUE}15`, color: LINKEDIN_BLUE }}>
                  <UserPlus size={11} />
                  {busy === 'conn' ? 'Queuing…' : 'Queue Connection'}
                </button>
              )}

              {/* Mark connected */}
              {record.connection_status === 'pending' && (
                <button onClick={() => act(MarkConnectedService, 'mkconn')} disabled={busy === 'mkconn'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100 disabled:opacity-50 transition-all">
                  <CheckCircle size={11} />
                  {busy === 'mkconn' ? 'Saving…' : 'Mark Connected'}
                </button>
              )}

              {/* Queue message */}
              {record.connection_status === 'connected' && record.message_status === 'not_sent' && (
                <button onClick={() => act(QueueMessageService, 'msg')} disabled={busy === 'msg'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 disabled:opacity-50 transition-all">
                  <Send size={11} />
                  {busy === 'msg' ? 'Queuing…' : 'Queue Message'}
                </button>
              )}

              {/* Mark message sent */}
              {record.message_status === 'queued' && (
                <button onClick={() => act(MarkMessageSentService, 'mksent')} disabled={busy === 'mksent'}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 text-xs font-semibold hover:bg-blue-100 disabled:opacity-50 transition-all">
                  <CheckCircle size={11} />
                  {busy === 'mksent' ? 'Saving…' : 'Mark Sent'}
                </button>
              )}

              {/* Record reply */}
              {record.message_status === 'sent' && (
                <button onClick={() => setReplyOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-50 text-violet-700 text-xs font-semibold hover:bg-violet-100 transition-all">
                  <MessageSquare size={11} /> Record Reply
                </button>
              )}

              {/* LinkedIn link */}
              {record.linkedin_url && (
                <a href={record.linkedin_url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                  style={{ background: `${LINKEDIN_BLUE}10`, color: LINKEDIN_BLUE }}>
                  <Linkedin size={11} /> Profile
                </a>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      <AnimatePresence>
        {replyOpen && (
          <ReplyModal record={record} onClose={() => setReplyOpen(false)}
            onSave={() => { setReplyOpen(false); onRefresh() }} />
        )}
      </AnimatePresence>
    </>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

const CONN_FILTERS = ['all', 'not_sent', 'pending', 'connected', 'rejected']
const MSG_FILTERS  = ['all', 'not_sent', 'queued', 'sent', 'replied']

export default function LinkedInIntegration() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [budget, setBudget] = useState(null)
  const [connFilter, setConnFilter] = useState('all')
  const [msgFilter, setMsgFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [showDiscovery, setShowDiscovery] = useState(false)
  const LIMIT = 20

  const loadBudget = () => {
    GetLinkedInBudgetService(d => setBudget(d), () => {})
  }

  const load = useCallback(() => {
    setLoading(true)
    const params = { page, limit: LIMIT }
    if (connFilter !== 'all') params.connection_status = connFilter
    if (msgFilter !== 'all')  params.message_status    = msgFilter
    GetLinkedInOutreachService(params,
      d => { setItems(d.items || []); setTotal(d.total || 0); setLoading(false) },
      () => setLoading(false)
    )
  }, [connFilter, msgFilter, page])

  useEffect(() => { load(); loadBudget() }, [load])
  useEffect(() => { setPage(1) }, [connFilter, msgFilter])

  const filtered = search.trim()
    ? items.filter(r =>
        (r.full_name || '').toLowerCase().includes(search.toLowerCase()) ||
        (r.company_name || '').toLowerCase().includes(search.toLowerCase())
      )
    : items

  const b = budget || {}

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-[1200px] mx-auto px-6 py-6 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: `${LINKEDIN_BLUE}18` }}>
              <Linkedin size={20} style={{ color: LINKEDIN_BLUE }} />
            </div>
            <div>
              <h1 className="text-xl font-black text-gray-900">LinkedIn Integration</h1>
              <p className="text-xs text-gray-400 mt-0.5">Manage outreach pipeline and daily budget</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={load}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 text-sm font-semibold hover:bg-gray-100 transition-all">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
            </button>
            <button onClick={() => setShowDiscovery(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 transition-all shadow-md"
              style={{ background: LINKEDIN_BLUE }}>
              <Zap size={14} /> Discover Companies
            </button>
          </div>
        </div>

        {/* Budget bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: 'Connections Today', used: b.connections_used ?? 0, limit: b.connections_limit ?? 15, color: LINKEDIN_BLUE },
            { label: 'Messages Today',    used: b.messages_used_today ?? 0, limit: 40, color: '#6172f3' },
            { label: 'Messages This Week', used: b.messages_used_week ?? 0, limit: 90, color: '#8b5cf6' },
          ].map(({ label, used, limit, color }) => {
            const pct = limit > 0 ? Math.min(100, Math.round(used / limit * 100)) : 0
            return (
              <div key={label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
                <div className="flex justify-between text-xs mb-2">
                  <span className="font-semibold text-gray-700">{label}</span>
                  <span className="text-gray-400">{used}/{limit}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all"
                    style={{ width: `${pct}%`, background: pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : color }} />
                </div>
                <p className="text-[11px] text-gray-400 mt-1.5">{limit - used} remaining</p>
              </div>
            )
          })}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl flex-1 min-w-48">
            <Search size={13} className="text-gray-400 flex-shrink-0" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search by name or company…"
              className="text-sm text-gray-700 bg-transparent border-none outline-none flex-1 min-w-0" />
          </div>

          {/* Connection filter */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl">
            <Filter size={12} className="text-gray-400" />
            <select value={connFilter} onChange={e => setConnFilter(e.target.value)}
              className="text-sm text-gray-700 bg-transparent border-none outline-none font-medium">
              {CONN_FILTERS.map(f => (
                <option key={f} value={f}>{f === 'all' ? 'All Connections' : CONN_STATUS[f]?.label || f}</option>
              ))}
            </select>
            <ChevronDown size={12} className="text-gray-400" />
          </div>

          {/* Message filter */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl">
            <MessageSquare size={12} className="text-gray-400" />
            <select value={msgFilter} onChange={e => setMsgFilter(e.target.value)}
              className="text-sm text-gray-700 bg-transparent border-none outline-none font-medium">
              {MSG_FILTERS.map(f => (
                <option key={f} value={f}>{f === 'all' ? 'All Messages' : MSG_STATUS[f]?.label || f}</option>
              ))}
            </select>
            <ChevronDown size={12} className="text-gray-400" />
          </div>

          <p className="text-xs text-gray-400 ml-auto">{total} profiles</p>
        </div>

        {/* List */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-28 rounded-xl bg-white border border-gray-100 animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24">
            <Linkedin size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
            <p className="text-base font-bold text-gray-400">No outreach records found</p>
            <p className="text-sm text-gray-400 mt-1">Run Company Discovery to populate your pipeline.</p>
            <button onClick={() => setShowDiscovery(true)}
              className="mt-5 flex items-center gap-2 px-6 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 transition-all mx-auto shadow-md"
              style={{ background: LINKEDIN_BLUE }}>
              <Zap size={14} /> Discover Companies
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {filtered.map(r => <OutreachRow key={r.id} record={r} onRefresh={load} />)}
            </AnimatePresence>
          </div>
        )}

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-4 py-2 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-40 transition-all">
              Previous
            </button>
            <span className="text-xs text-gray-400">Page {page} of {Math.ceil(total / LIMIT)}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / LIMIT)}
              className="px-4 py-2 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-100 disabled:opacity-40 transition-all">
              Next
            </button>
          </div>
        )}
      </div>

      <AnimatePresence>
        {showDiscovery && (
          <DiscoveryModal
            onClose={() => setShowDiscovery(false)}
            onStarted={() => { setShowDiscovery(false); load() }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

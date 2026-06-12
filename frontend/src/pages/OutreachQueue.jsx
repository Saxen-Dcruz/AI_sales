import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, CheckCircle, X, MessageSquare, Zap, RefreshCw,
  ChevronDown, Filter, ThumbsUp, ThumbsDown, Eye, Edit3,
  Building2, User, Clock, CornerDownRight, Inbox,
} from 'lucide-react'
import {
  GetOutreachQueueService, ApproveOutreachService, SendOutreachService,
  RejectOutreachService, SetInterestService, GetOutreachThreadService,
  SendManualReplyService, GenerateAIReplyService, GetCampaignsService,
} from '../services/ApiService'

// ── Constants ────────────────────────────────────────────────────────────────

const STATUS = {
  pending:       { label: 'Pending',      bg: 'bg-gray-100 text-gray-600',      dot: '#9ca3af' },
  approved:      { label: 'Approved',     bg: 'bg-blue-100 text-blue-700',       dot: '#3b82f6' },
  sent:          { label: 'Sent',         bg: 'bg-emerald-100 text-emerald-700', dot: '#10b981' },
  replied:       { label: 'Replied',      bg: 'bg-amber-100 text-amber-700',     dot: '#f59e0b' },
  interested:    { label: 'Interested',   bg: 'bg-violet-100 text-violet-700',   dot: '#8b5cf6' },
  not_interested:{ label: 'Ignored',      bg: 'bg-red-100 text-red-600',         dot: '#ef4444' },
}

const TABS = ['all', 'pending', 'approved', 'sent', 'replied', 'interested', 'not_interested']

// ── Draft Modal ───────────────────────────────────────────────────────────────

function DraftModal({ item, onClose, onApprove, onSend, onReject }) {
  const [body, setBody] = useState(item.ai_draft || '')
  const [loading, setLoading] = useState(null)

  const contact = item.contact || {}
  const company = contact.company || {}
  const campaign = item.campaign || {}

  const handleApprove = () => {
    setLoading('approve')
    ApproveOutreachService(item.id, { edit_body: body },
      () => { setLoading(null); onApprove() },
      () => setLoading(null)
    )
  }

  const handleSend = () => {
    setLoading('send')
    ApproveOutreachService(item.id, { edit_body: body }, () => {
      SendOutreachService(item.id,
        () => { setLoading(null); onSend() },
        () => setLoading(null)
      )
    }, () => setLoading(null))
  }

  const handleReject = () => {
    setLoading('reject')
    RejectOutreachService(item.id, () => { setLoading(null); onReject() }, () => setLoading(null))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h3 className="text-sm font-black text-gray-900">Review Draft</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              To: <span className="font-semibold text-gray-700">{contact.name}</span>
              {contact.job_title && <> · {contact.job_title}</>}
              {company.name && <> · {company.name}</>}
            </p>
            {campaign.name && <p className="text-[11px] text-indigo-500 font-semibold mt-0.5">Campaign: {campaign.name}</p>}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>
        </div>

        {/* Subject preview */}
        {campaign.email_subject && (
          <div className="px-6 py-2.5 border-b border-gray-100 bg-gray-50">
            <p className="text-xs text-gray-400">Subject: <span className="font-semibold text-gray-700">{campaign.email_subject}</span></p>
          </div>
        )}

        {/* Draft body editor */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {item.ai_draft ? (
            <textarea
              value={body}
              onChange={e => setBody(e.target.value)}
              rows={14}
              className="w-full text-sm text-gray-700 leading-relaxed bg-gray-50 border border-gray-200 rounded-xl p-4 resize-none focus:outline-none focus:border-indigo-400 focus:bg-white font-mono"
            />
          ) : (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
              No draft generated yet. Go back and click AI Drafts on the campaign.
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <button onClick={handleReject} disabled={!!loading}
            className="px-4 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50 disabled:opacity-40 transition-all">
            {loading === 'reject' ? 'Rejecting…' : 'Reject'}
          </button>
          <div className="flex-1" />
          <button onClick={handleApprove} disabled={!!loading || !body.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl border border-blue-200 text-blue-700 text-sm font-semibold hover:bg-blue-50 disabled:opacity-40 transition-all">
            <CheckCircle size={14} />
            {loading === 'approve' ? 'Approving…' : 'Approve'}
          </button>
          <button onClick={handleSend} disabled={!!loading || !body.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-40 transition-all shadow-md shadow-indigo-200">
            <Send size={14} />
            {loading === 'send' ? 'Sending…' : 'Approve & Send'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ── Thread Modal ───────────────────────────────────────────────────────────────

function EmailMessage({ msg, contact, isLast }) {
  const [collapsed, setCollapsed] = useState(!isLast)
  const isOut = msg.direction === 'outbound'
  const senderName = isOut ? 'RDL Technologies' : (contact.name || 'Customer')
  const senderInitial = isOut ? 'R' : (contact.name?.[0] || 'C')
  const timeStr = msg.sent_at ? new Date(msg.sent_at).toLocaleString() : ''

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${isLast ? 'border-indigo-200 shadow-sm' : 'border-gray-200'}`}>
      {/* Email row header — always visible */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${collapsed ? 'hover:bg-gray-50' : isOut ? 'bg-indigo-50' : 'bg-amber-50'}`}
      >
        <div className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-[11px] font-black text-white ${isOut ? 'bg-indigo-500' : 'bg-amber-500'}`}>
          {senderInitial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-bold ${isOut ? 'text-indigo-800' : 'text-gray-800'}`}>{senderName}</span>
            {msg.ai_generated && isOut && (
              <span className="flex items-center gap-0.5 text-[10px] text-violet-500 font-semibold">
                <Zap size={9} /> AI
              </span>
            )}
          </div>
          {collapsed && (
            <p className="text-[11px] text-gray-400 truncate mt-0.5">
              {(msg.content || '').slice(0, 80)}{msg.content?.length > 80 ? '…' : ''}
            </p>
          )}
        </div>
        <span className="text-[10px] text-gray-400 flex-shrink-0">{timeStr}</span>
        <ChevronDown size={14} className={`text-gray-400 flex-shrink-0 transition-transform ${collapsed ? '' : 'rotate-180'}`} />
      </button>

      {/* Email body — expanded */}
      {!collapsed && (
        <div className={`px-5 py-4 border-t ${isOut ? 'border-indigo-100 bg-white' : 'border-amber-100 bg-white'}`}>
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>
      )}
    </div>
  )
}

function ThreadModal({ item, onClose, onReply }) {
  const [thread, setThread] = useState(null)
  const [loadingThread, setLoadingThread] = useState(true)
  const [replyBody, setReplyBody] = useState('')
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [interest, setInterest] = useState(item.status)

  const contact = item.contact || {}
  const company = contact.company || {}
  const campaign = item.campaign || {}

  const loadThread = useCallback(() => {
    setLoadingThread(true)
    GetOutreachThreadService(item.id,
      d => { setThread(d); setLoadingThread(false) },
      () => setLoadingThread(false)
    )
  }, [item.id])

  useEffect(() => { loadThread() }, [loadThread])

  const handleGenerateReply = () => {
    setGenerating(true)
    GenerateAIReplyService(item.id,
      d => { setReplyBody(d.draft || ''); setGenerating(false) },
      () => setGenerating(false)
    )
  }

  const handleSendReply = () => {
    if (!replyBody.trim()) return
    setSending(true)
    SendManualReplyService(item.id, replyBody,
      () => { setSending(false); setReplyBody(''); loadThread(); onReply() },
      () => setSending(false)
    )
  }

  const handleInterest = (status) => {
    SetInterestService(item.id, status, () => setInterest(status), () => {})
  }

  const msgs = thread?.messages || []
  const subject = campaign.email_subject || item.subject || 'Email Thread'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[92vh] flex flex-col">

        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-black text-gray-900 truncate">
                {msgs.length > 0 ? `Re: ${subject}` : subject}
              </h3>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">SALES</span>
                <span className="text-[10px] text-gray-400">
                  {contact.name}{contact.job_title && ` · ${contact.job_title}`}{company.name && ` · ${company.name}`}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button onClick={() => handleInterest('interested')}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${interest === 'interested' ? 'bg-violet-600 text-white' : 'border border-violet-200 text-violet-600 hover:bg-violet-50'}`}>
                <ThumbsUp size={12} /> Interested
              </button>
              <button onClick={() => handleInterest('not_interested')}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${interest === 'not_interested' ? 'bg-red-500 text-white' : 'border border-red-200 text-red-500 hover:bg-red-50'}`}>
                <ThumbsDown size={12} /> Pass
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 ml-1"><X size={16} /></button>
            </div>
          </div>

          {/* From / Date / Account row */}
          {msgs.length > 0 && (() => {
            const last = msgs[msgs.length - 1]
            const isLastOut = last.direction === 'outbound'
            return (
              <div className="mt-3 flex items-center gap-6 text-[11px] text-gray-500 flex-wrap">
                <span><span className="text-gray-400">FROM</span> <span className="font-semibold text-gray-700">{isLastOut ? 'RDL Technologies' : contact.name}</span></span>
                {last.sent_at && <span><span className="text-gray-400">DATE</span> <span className="font-semibold text-gray-700">{new Date(last.sent_at).toLocaleString()}</span></span>}
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" /><span className="font-semibold text-gray-700">{item.email || contact.email || ''}</span></span>
              </div>
            )
          })()}
        </div>

        {/* Thread messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
          {loadingThread ? (
            <div className="flex items-center justify-center h-24 text-gray-400 text-sm">Loading thread…</div>
          ) : msgs.length === 0 ? (
            <div className="flex items-center justify-center h-24 text-gray-400 text-sm">No messages in this thread yet.</div>
          ) : (
            msgs.map((msg, i) => (
              <EmailMessage
                key={msg.id || i}
                msg={msg}
                contact={contact}
                isLast={i === msgs.length - 1}
              />
            ))
          )}

          {/* AI summary */}
          {thread?.ai_summary && (
            <div className="mt-2 p-3 rounded-xl bg-violet-50 border border-violet-100">
              <p className="text-[10px] font-black text-violet-500 uppercase tracking-wide mb-1">AI Summary</p>
              <p className="text-xs text-violet-800">{thread.ai_summary}</p>
            </div>
          )}
        </div>

        {/* Reply composer */}
        <div className="px-6 py-4 border-t border-gray-100 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-gray-600 flex items-center gap-1.5">
              <CornerDownRight size={12} /> Reply
            </p>
            <button onClick={handleGenerateReply} disabled={generating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-50 text-violet-700 text-xs font-semibold hover:bg-violet-100 disabled:opacity-50 transition-all">
              <Zap size={11} className={generating ? 'animate-pulse' : ''} />
              {generating ? 'Generating…' : 'AI Reply'}
            </button>
          </div>
          <textarea
            value={replyBody}
            onChange={e => setReplyBody(e.target.value)}
            rows={4}
            placeholder="Write your reply here, or click AI Reply to generate one…"
            className="w-full text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-xl p-3 resize-none focus:outline-none focus:border-indigo-400 focus:bg-white"
          />
          <div className="flex justify-end">
            <button onClick={handleSendReply} disabled={sending || !replyBody.trim()}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-40 transition-all shadow-md shadow-indigo-200">
              <Send size={14} />
              {sending ? 'Sending…' : 'Send Reply'}
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// ── Queue Card ────────────────────────────────────────────────────────────────

function QueueCard({ item, onRefresh }) {
  const [draftOpen, setDraftOpen] = useState(false)
  const [threadOpen, setThreadOpen] = useState(false)
  const [sending, setSending] = useState(false)

  const contact = item.contact || {}
  const company = contact.company || {}
  const statusCfg = STATUS[item.status] || STATUS.pending
  const hasDraft = !!item.ai_draft
  const hasThread = ['sent', 'replied', 'interested', 'not_interested'].includes(item.status)
  const canSend = item.status === 'approved' && hasDraft

  const handleQuickSend = () => {
    setSending(true)
    SendOutreachService(item.id, () => { setSending(false); onRefresh() }, () => setSending(false))
  }

  return (
    <>
      <motion.div layout className="bg-white rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow p-4">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-black text-white"
            style={{ background: 'linear-gradient(135deg, #6172f3, #818cf8)' }}>
            {contact.name?.[0] || '?'}
          </div>

          <div className="flex-1 min-w-0">
            {/* Name + status */}
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <p className="text-sm font-black text-gray-900 truncate">{contact.name || 'Unknown'}</p>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusCfg.bg}`}>{statusCfg.label}</span>
            </div>

            {/* Role + company */}
            <div className="flex items-center gap-3 text-xs text-gray-400 mb-2">
              {contact.job_title && (
                <span className="flex items-center gap-1"><User size={10} />{contact.job_title}</span>
              )}
              {company.name && (
                <span className="flex items-center gap-1"><Building2 size={10} />{company.name}</span>
              )}
            </div>

            {/* Draft preview */}
            {hasDraft && (
              <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 line-clamp-2 mb-3">
                {item.ai_draft.slice(0, 140)}{item.ai_draft.length > 140 ? '…' : ''}
              </p>
            )}
            {!hasDraft && item.status === 'pending' && (
              <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-1.5 mb-3 border border-amber-100">
                No draft yet — generate AI drafts from the campaign page.
              </p>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* View/edit draft */}
              {(item.status === 'pending' || item.status === 'approved') && hasDraft && (
                <button onClick={() => setDraftOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 transition-all">
                  <Edit3 size={11} />
                  {item.status === 'approved' ? 'Edit Draft' : 'Review Draft'}
                </button>
              )}

              {/* Quick send (already approved) */}
              {canSend && (
                <button onClick={handleQuickSend} disabled={sending}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100 disabled:opacity-50 transition-all">
                  <Send size={11} />
                  {sending ? 'Sending…' : 'Send Now'}
                </button>
              )}

              {/* View thread */}
              {hasThread && (
                <button onClick={() => setThreadOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 text-amber-700 text-xs font-semibold hover:bg-amber-100 transition-all">
                  <MessageSquare size={11} /> Thread
                </button>
              )}

              {/* Replied: generate AI reply via thread */}
              {item.status === 'replied' && (
                <button onClick={() => setThreadOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-50 text-violet-700 text-xs font-semibold hover:bg-violet-100 transition-all">
                  <Zap size={11} /> Reply
                </button>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      <AnimatePresence>
        {draftOpen && (
          <DraftModal
            item={item}
            onClose={() => setDraftOpen(false)}
            onApprove={() => { setDraftOpen(false); onRefresh() }}
            onSend={() => { setDraftOpen(false); onRefresh() }}
            onReject={() => { setDraftOpen(false); onRefresh() }}
          />
        )}
        {threadOpen && (
          <ThreadModal
            item={item}
            onClose={() => setThreadOpen(false)}
            onReply={onRefresh}
          />
        )}
      </AnimatePresence>
    </>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function OutreachQueue() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('all')
  const [campaigns, setCampaigns] = useState([])
  const [selectedCampaign, setSelectedCampaign] = useState('')
  const [page, setPage] = useState(1)
  const LIMIT = 30

  const load = useCallback(() => {
    setLoading(true)
    const params = { page, limit: LIMIT }
    if (activeTab !== 'all') params.status = activeTab
    if (selectedCampaign) params.campaign_id = selectedCampaign
    GetOutreachQueueService(params,
      d => { setItems(d.items || []); setTotal(d.total || 0); setLoading(false) },
      () => setLoading(false)
    )
  }, [activeTab, selectedCampaign, page])

  useEffect(() => { load() }, [load])
  useEffect(() => { setPage(1) }, [activeTab, selectedCampaign])

  useEffect(() => {
    GetCampaignsService(d => setCampaigns(d || []), () => {})
  }, [])

  const counts = {}
  TABS.forEach(t => {
    counts[t] = t === 'all' ? total : (t === activeTab ? total : '—')
  })

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-[1200px] mx-auto px-6 py-6 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black text-gray-900">Outreach Queue</h1>
            <p className="text-xs text-gray-400 mt-0.5">Review AI drafts, send emails, and manage conversations</p>
          </div>
          <button onClick={load}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-gray-600 text-sm font-semibold hover:bg-gray-100 transition-all">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl">
            <Filter size={13} className="text-gray-400" />
            <select value={selectedCampaign} onChange={e => setSelectedCampaign(e.target.value)}
              className="text-sm text-gray-700 bg-transparent border-none outline-none font-medium">
              <option value="">All Campaigns</option>
              {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <ChevronDown size={12} className="text-gray-400" />
          </div>

          <p className="text-xs text-gray-400 ml-auto">
            {total} contact{total !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Status tabs */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {TABS.map(tab => {
            const cfg = STATUS[tab]
            return (
              <button key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
                  activeTab === tab
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}>
                {cfg && (
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${activeTab === tab ? 'bg-white/70' : ''}`}
                    style={activeTab !== tab ? { background: cfg.dot } : {}} />
                )}
                {cfg ? cfg.label : 'All'}
              </button>
            )
          })}
        </div>

        {/* Queue list */}
        {loading ? (
          <div className="grid gap-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-32 rounded-xl bg-white border border-gray-100 animate-pulse" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-24">
            <Inbox size={40} className="mx-auto text-gray-200 mb-3" />
            <p className="text-base font-bold text-gray-400">No contacts in this view</p>
            <p className="text-sm text-gray-400 mt-1">
              {activeTab === 'pending'
                ? 'Add contacts to a campaign, then generate AI drafts from the Campaigns page.'
                : 'Try a different status filter or campaign.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            <AnimatePresence>
              {items.map(item => (
                <QueueCard key={item.id} item={item} onRefresh={load} />
              ))}
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
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw, Search, Mail, MailOpen, AlertCircle,
  CheckCircle, Archive, Send, Users, Star, Tag, ChevronRight,
  X, Zap
} from 'lucide-react'
import { GetGmailMessagesService, SyncGmailService, ApproveDraftService, ResolveEmailService, DiscardDraftService, GenerateDraftService, SendEmailService, GetEmailByIdService } from '../services/ApiService'
import { useCallback, useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GetGmailMessagesService, SyncGmailService } from '../services/ApiService'

// ─── Config ──────────────────────────────────────────────────────────────────

const LABEL_CONFIG = {
  Sales:         { bg: 'bg-emerald-50',  text: 'text-emerald-700', border: 'border-l-emerald-400', dot: 'bg-emerald-400', badge: 'bg-emerald-100 text-emerald-700' },
  Support:       { bg: 'bg-amber-50',    text: 'text-amber-700',   border: 'border-l-amber-400',   dot: 'bg-amber-400',   badge: 'bg-amber-100 text-amber-700' },
  Grievance:     { bg: 'bg-red-50',      text: 'text-red-700',     border: 'border-l-red-400',     dot: 'bg-red-400',     badge: 'bg-red-100 text-red-700' },
  Transactional: { bg: 'bg-blue-50',     text: 'text-blue-700',    border: 'border-l-blue-300',    dot: 'bg-blue-300',    badge: 'bg-blue-100 text-blue-700' },
  Promotional:   { bg: 'bg-purple-50',   text: 'text-purple-700',  border: 'border-l-purple-300',  dot: 'bg-purple-300',  badge: 'bg-purple-100 text-purple-700' },
  Personal:      { bg: 'bg-pink-50',     text: 'text-pink-700',    border: 'border-l-pink-300',    dot: 'bg-pink-300',    badge: 'bg-pink-100 text-pink-700' },
  Unclassified:  { bg: 'bg-gray-50',     text: 'text-gray-600',    border: 'border-l-gray-300',    dot: 'bg-gray-300',    badge: 'bg-gray-100 text-gray-600' },
}

const STATUS_CONFIG = {
  new:           { icon: Mail,         color: 'text-blue-500',  label: 'New' },
  classified:    { icon: Tag,          color: 'text-gray-400',  label: 'Classified' },
  draft_ready:   { icon: Star,         color: 'text-amber-500', label: 'Draft Ready' },
  pending_human: { icon: AlertCircle,  color: 'text-red-500',   label: 'Needs Review' },
  replied:       { icon: CheckCircle,  color: 'text-emerald-500', label: 'Replied' },
  archived:      { icon: Archive,      color: 'text-gray-400',  label: 'Archived' },
  ignored:       { icon: X,           color: 'text-gray-300',  label: 'Ignored' },
}


const TABS = [
  { key: '',              label: 'All',          icon: Mail },
  { key: 'Sales',        label: 'Sales',         icon: Zap },
  { key: 'Support',      label: 'Support',       icon: Users },
  { key: 'Grievance',    label: 'Grievance',     icon: AlertCircle },
  { key: 'needs_human',  label: 'Needs Review',  icon: Star },
  { key: 'draft_ready',  label: 'Draft Ready',   icon: Send },
]

// ─── Helpers ─────────────────────────────────────────────────────────────────

function relTime(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso)
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}d ago`
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function senderInitial(sender) {
  if (!sender) return '?'
  const name = sender.split('<')[0].trim() || sender.split('@')[0]
  return name[0]?.toUpperCase() || '?'
}

function senderName(sender) {
  if (!sender) return 'Unknown'
  const match = sender.match(/^(.+?)\s*</)
  return match ? match[1].trim() : sender.split('@')[0]
}

// ─── Email row ───────────────────────────────────────────────────────────────

function EmailRow({ email, selected, onClick }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const statusCfg = STATUS_CONFIG[email.status] || STATUS_CONFIG.classified
  const StatusIcon = statusCfg.icon
  const isUnread = email.status === 'new'

  return (
    <button onClick={onClick}
      className={`w-full text-left border-l-4 px-4 py-3 transition-all
        ${selected ? 'bg-blue-50 border-l-blue-500' : `hover:bg-gray-50 ${labelCfg.border}`}
        ${email.needs_human ? 'bg-red-50/30' : ''}
        border-b border-gray-100 last:border-b-0`}>
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white
          ${email.label === 'Sales' ? 'bg-emerald-500' :
            email.label === 'Support' ? 'bg-amber-500' :
            email.label === 'Grievance' ? 'bg-red-500' :
            email.label === 'Transactional' ? 'bg-blue-400' :
            'bg-gray-400'}`}>
          {senderInitial(email.sender)}
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className={`text-xs truncate ${isUnread ? 'font-bold text-gray-900' : 'font-medium text-gray-700'}`}>
              {senderName(email.sender)}
            </span>
            <span className="text-[10px] text-gray-400 flex-shrink-0">{relTime(email.received_at)}</span>
          </div>
          {/* Subject */}
          <p className={`text-[11px] truncate ${isUnread ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
            {email.subject || '(no subject)'}
          </p>
          {/* Bottom row: badges */}
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${labelCfg.badge}`}>
              {email.label || 'Unclassified'}
            </span>
            {email.needs_human && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-red-100 text-red-600">
                Review
              </span>
            )}
            {email.status === 'draft_ready' && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-600">
                Draft
              </span>
            )}
            <StatusIcon size={10} className={`${statusCfg.color} ml-auto flex-shrink-0`} />
          </div>
        </div>

        <ChevronRight size={12} className={`flex-shrink-0 transition-colors ${selected ? 'text-blue-400' : 'text-gray-300'}`} />
      </div>
    </button>
  )
}

// ─── Email detail ─────────────────────────────────────────────────────────────

function EmailDetail({ email, onRefresh }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const [acting, setActing] = useState(null)
  const [note, setNote] = useState('')
  const [done, setDone] = useState(false)

  const handleApprove = () => {
    setActing('approve')
    ApproveDraftService(email.id, {},
      () => { setActing(null); setDone(true); setTimeout(onRefresh, 800) },
      (_s, err) => { setActing(null); alert('Failed: ' + err) }
    )
  }

  const handleResolve = () => {
    setActing('resolve')
    ResolveEmailService(email.id, { resolved_by: 'agent', note },
      () => { setActing(null); setDone(true); setTimeout(onRefresh, 800) },
      (_s, err) => { setActing(null); alert('Failed: ' + err) }
    )
  }

  const handleDiscard = () => {
    setActing('discard')
    DiscardDraftService(email.id,
      () => { setActing(null); setDone(true); setTimeout(onRefresh, 800) },
      (_s, err) => { setActing(null); alert('Failed: ' + err) }
    )
  }

  if (done) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-center p-8">
        <CheckCircle size={32} className="text-emerald-500" />
        <p className="text-sm font-semibold text-gray-700">Action completed</p>
        <p className="text-xs text-gray-400">Refreshing inbox...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className={`px-6 py-4 border-b border-gray-100 ${labelCfg.bg}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-gray-900 leading-snug">{email.subject || '(no subject)'}</h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${labelCfg.badge}`}>
                {email.label}
              </span>
              {email.needs_human && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-600">
                  Needs Review
                </span>
              )}
              {email.classifier_confidence && (
                <span className="text-[10px] text-gray-400">
                  {typeof email.classifier_confidence === 'number'
                    ? `${Math.round(email.classifier_confidence * 100)}% confidence`
                    : `${email.classifier_confidence} confidence`}
                </span>
              )}
            </div>
          </div>
        </div>
        {/* From / Date */}
        <div className="mt-3 text-xs text-gray-500 space-y-0.5">
          <p><span className="font-medium">From:</span> {email.sender}</p>
          {email.received_at && (
            <p><span className="font-medium">Date:</span> {new Date(email.received_at).toLocaleString()}</p>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">

        {/* Classifier reasoning */}
        {email.classifier_reasoning && (
          <div className="p-3 rounded-xl bg-gray-50 border border-gray-100">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">AI Classification</p>
            <p className="text-xs text-gray-600 leading-relaxed">{email.classifier_reasoning}</p>
          </div>
        )}

        {/* Email body */}
        {email.body_text && (
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">Message</p>
            <div className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap bg-white border border-gray-100 rounded-xl p-4 max-h-48 overflow-y-auto">
              {email.body_text}
            </div>
          </div>
        )}

        {/* AI Draft */}
        {email.ai_draft && (
          <div className={`rounded-xl border p-4 ${LABEL_CONFIG.Sales.bg} border-emerald-200`}>
            <p className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wide mb-2">AI Draft Reply</p>
            <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{email.ai_draft}</p>
          </div>
        )}

        {/* Gaps */}
        {email.followup_gaps?.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-amber-600 uppercase tracking-wide mb-2">
              Knowledge Gaps ({email.followup_gaps.filter(g => !g.resolved).length} unresolved)
            </p>
            <div className="space-y-1.5">
              {email.followup_gaps.map((gap, i) => {
                const q = typeof gap === 'string' ? gap : gap.question
                const resolved = typeof gap === 'object' && gap.resolved
                return (
                  <div key={i} className={`flex items-start gap-2 p-2.5 rounded-lg text-xs
                    ${resolved ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                    {resolved ? <CheckCircle size={12} className="mt-0.5 flex-shrink-0" /> :
                      <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />}
                    <span>{q}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Resolution note (for Grievance/Support) */}
        {(email.label === 'Grievance' || email.label === 'Support') && email.status !== 'replied' && !email.resolved_at && (
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">Resolution Note</p>
            <textarea value={note} onChange={e => setNote(e.target.value)}
              placeholder="Add a note for the customer resolution email..."
              className="w-full text-xs text-gray-700 border border-gray-200 rounded-xl p-3 resize-none h-20 focus:outline-none focus:border-blue-400 transition-all" />
          </div>
        )}

      </div>

      {/* Action bar */}
      <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/50">
        <div className="flex gap-2 flex-wrap">
          {email.status === 'draft_ready' && email.ai_draft && (
            <>
              <button onClick={handleApprove} disabled={acting === 'approve'}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all disabled:opacity-60">
                <Send size={12} />
                {acting === 'approve' ? 'Sending...' : 'Approve & Send'}
              </button>
              <button onClick={handleDiscard} disabled={acting === 'discard'}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gray-100 text-gray-600 text-xs font-medium hover:bg-gray-200 transition-all disabled:opacity-60">
                <X size={12} />
                Discard
              </button>
            </>
          )}
          {(email.label === 'Support' || email.label === 'Grievance') &&
            email.status !== 'replied' && !email.resolved_at && (
            <button onClick={handleResolve} disabled={acting === 'resolve'}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-all disabled:opacity-60">
              <CheckCircle size={12} />
              {acting === 'resolve' ? 'Resolving...' : 'Mark Resolved'}
            </button>
          )}
          {email.status === 'replied' && (
            <div className="flex items-center gap-2 text-xs text-emerald-600 font-medium">
              <CheckCircle size={13} />
              Replied
            </div>
          )}
          {email.resolved_at && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <CheckCircle size={13} className="text-emerald-500" />
              Resolved by {email.resolved_by} · {relTime(email.resolved_at)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Compose Modal ────────────────────────────────────────────────────────────

function ComposeModal({ onClose, onSent }) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [draft, setDraft] = useState('')
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [step, setStep] = useState('compose') // compose | draft

  const handleGenerate = () => {
    if (!to || !subject) return
    setGenerating(true)
    GenerateDraftService({ to, subject, body },
      (data) => { setDraft(data.draft); setStep('draft'); setGenerating(false) },
      (_s, err) => { alert('Draft generation failed: ' + err); setGenerating(false) }
    )
  }

  const handleSend = () => {
    if (!to || !subject || !draft) return
    setSending(true)
    SendEmailService({ to, subject, body: draft },
      () => { setSending(false); onSent(); onClose() },
      (_s, err) => { alert('Send failed: ' + err); setSending(false) }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />

      <motion.div initial={{ opacity: 0, y: 40, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 40 }} transition={{ type: 'spring', damping: 28 }}
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl z-10 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-50">
              <Send size={15} className="text-blue-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900">New Email</h2>
              <p className="text-[10px] text-gray-400">
                {step === 'compose' ? 'Fill in details then generate an AI draft' : 'Review and edit the AI draft before sending'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 transition-all">
            <X size={15} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* To + Subject */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-gray-400 w-14 flex-shrink-0">To</span>
              <input value={to} onChange={e => setTo(e.target.value)} type="email"
                placeholder="customer@example.com"
                className="flex-1 text-sm text-gray-800 border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-400 transition-all" />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-gray-400 w-14 flex-shrink-0">Subject</span>
              <input value={subject} onChange={e => setSubject(e.target.value)}
                placeholder="Re: Product Inquiry"
                className="flex-1 text-sm text-gray-800 border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-400 transition-all" />
            </div>
          </div>

          {/* Context body (always visible) */}
          <div>
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
              Customer's message / context for AI
            </p>
            <textarea value={body} onChange={e => setBody(e.target.value)} rows={3}
              placeholder="Paste the customer's question or describe what the email is about..."
              className="w-full text-sm text-gray-700 border border-gray-200 rounded-xl px-3 py-2.5 resize-none focus:outline-none focus:border-blue-400 transition-all" />
          </div>

          {/* AI Draft section */}
          <AnimatePresence>
            {step === 'draft' && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2.5 border-b border-emerald-200">
                    <p className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide">
                      AI Draft — edit before sending
                    </p>
                    <button onClick={() => setStep('compose')}
                      className="text-[10px] text-emerald-600 hover:text-emerald-800 underline">
                      Regenerate
                    </button>
                  </div>
                  <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={8}
                    className="w-full text-sm text-gray-800 bg-transparent px-4 py-3 resize-none focus:outline-none" />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/60">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 transition-colors">
            Discard
          </button>
          <div className="flex items-center gap-2">
            {step === 'compose' ? (
              <button onClick={handleGenerate} disabled={!to || !subject || generating}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all disabled:opacity-50">
                <Zap size={13} className={generating ? 'animate-pulse' : ''} />
                {generating ? 'Generating...' : 'Generate AI Draft'}
              </button>
            ) : (
              <>
                <button onClick={() => setStep('compose')}
                  className="px-4 py-2 rounded-xl bg-gray-100 text-gray-600 text-sm font-medium hover:bg-gray-200 transition-all">
                  Edit Details
                </button>
                <button onClick={handleSend} disabled={!draft || sending}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition-all disabled:opacity-50">
                  <Send size={13} />
                  {sending ? 'Sending...' : 'Send Email'}
                </button>
              </>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const PAGE_SIZE = 30

export default function GmailIntegration() {
  const location = useLocation()
  const [emails, setEmails] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [activeTab, setActiveTab] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [directEmail, setDirectEmail] = useState(null) // email fetched directly from gaps nav
  const [composeOpen, setComposeOpen] = useState(false)

  // When navigated from GapsPage with a specific email to show
  useEffect(() => {
    const emailId = location.state?.selectEmailId
    if (!emailId) return
    GetEmailByIdService(emailId,
      (data) => { setDirectEmail(data); setSelected(data.id) },
      () => {}
    )
  }, [location.state])

  const fetchEmails = useCallback(() => {
    setLoading(true)
    const params = { page, limit: PAGE_SIZE }
    if (activeTab === 'needs_human') params.needs_human = true
    else if (activeTab === 'draft_ready') params.status = 'draft_ready'
    else if (activeTab) params.label = activeTab

    GetGmailMessagesService(params,
      (data) => { setEmails(data?.items || []); setTotal(data?.total || 0); setLoading(false) },
      () => setLoading(false)
    )
  }, [page, activeTab])

  useEffect(() => { fetchEmails() }, [fetchEmails])
  useEffect(() => { setPage(1); setSelected(null) }, [activeTab])

  const handleSync = () => {
    syncMutation.mutate()
  }

  // 3. Smart Background Sync Polling (Every 60s & on Window Focus)
  useQuery({
    queryKey: ['backgroundSync'],
    queryFn: () => new Promise((resolve, reject) => {
      SyncGmailService(
        () => {
          queryClient.invalidateQueries({ queryKey: ['emails'] })
          resolve(true)
        },
        (s, err) => reject(new Error(err))
      )
    }),
    refetchInterval: 60000,
    refetchOnWindowFocus: true,
  })

  useEffect(() => { setPage(1); setSelected(null) }, [filter])

  const syncing = syncMutation.isPending

  const filtered = search
    ? emails.filter(e =>
        (e.subject || '').toLowerCase().includes(search.toLowerCase()) ||
        (e.sender || '').toLowerCase().includes(search.toLowerCase())
      )
    : emails

  // directEmail is set when navigated from GapsPage — may not be in the current paginated list
  const selectedEmail = selected
    ? (directEmail?.id === selected ? directEmail : emails.find(e => e.id === selected))
    : null

  // Stats
  const needsReview = emails.filter(e => e.needs_human).length
  const draftReady = emails.filter(e => e.status === 'draft_ready').length

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">

      {/* Header + stats */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Gmail Inbox</h1>
          <p className="text-xs text-gray-400">{total} emails · auto-classified by AI</p>
        </div>
        <div className="flex items-center gap-2">
          {needsReview > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-red-100 text-red-600">
              {needsReview} need review
            </span>
          )}
          {draftReady > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-600">
              {draftReady} drafts ready
            </span>
          )}
          <button onClick={fetchEmails}
            className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-400 hover:bg-gray-100 transition-all">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={handleSync} disabled={syncing}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-all disabled:opacity-60">
            <RefreshCw size={13} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync'}
          </button>
          <button onClick={() => setComposeOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all">
            <Send size={13} />
            Compose
          </button>
        </div>
      </div>

      {/* Main two-panel layout */}
      <div className="flex gap-0 glass-card overflow-hidden" style={{ height: '72vh' }}>

        {/* Left: list */}
        <div className="w-80 flex-shrink-0 flex flex-col border-r border-gray-100">
          {/* Tabs */}
          <div className="overflow-x-auto border-b border-gray-100">
            <div className="flex min-w-max">
              {TABS.map(tab => {
                const Icon = tab.icon
                return (
                  <button key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-1.5 px-3 py-2.5 text-[10px] font-semibold border-b-2 transition-all whitespace-nowrap
                      ${activeTab === tab.key
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-400 hover:text-gray-600'}`}>
                    <Icon size={11} />
                    {tab.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Search */}
          <div className="px-3 py-2 border-b border-gray-100">
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search emails..."
                className="w-full pl-7 pr-3 py-1.5 text-xs rounded-lg bg-gray-50 border border-gray-200 text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-blue-400 transition-all" />
            </div>
          </div>

          {/* Email list */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex justify-center py-12 text-gray-400 text-xs">Loading...</div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 gap-2">
                <Mail size={24} className="text-gray-200" />
                <p className="text-xs text-gray-400">No emails found</p>
              </div>
            ) : (
              <AnimatePresence>
                {filtered.map(email => (
                  <motion.div key={email.id}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}>
                    <EmailRow
                      email={email}
                      selected={selected === email.id}
                      onClick={() => setSelected(selected === email.id ? null : email.id)}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>

          {/* Pagination */}
          {total > PAGE_SIZE && (
            <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 bg-gray-50/50">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                className="text-[10px] text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed">
                ← Prev
              </button>
              <span className="text-[10px] text-gray-400">{page} / {Math.ceil(total / PAGE_SIZE)}</span>
              <button disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)}
                className="text-[10px] text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed">
                Next →
              </button>
            </div>
          )}
        </div>

        {/* Right: detail */}
        <div className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            {selectedEmail ? (
              <motion.div key={selectedEmail.id} className="h-full"
                initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); setSelected(null) }} />
              </motion.div>
            ) : (
              <motion.div key="empty" className="flex flex-col items-center justify-center h-full gap-3 text-center p-8"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <MailOpen size={36} className="text-gray-200" />
                <p className="text-sm font-medium text-gray-400">Select an email to read</p>
                <div className="mt-2 grid grid-cols-2 gap-2 w-full max-w-xs">
                  {Object.entries(LABEL_CONFIG).filter(([k]) => k !== 'Unclassified').map(([label, cfg]) => {
                    const count = emails.filter(e => e.label === label).length
                    if (!count) return null
                    return (
                      <button key={label} onClick={() => setActiveTab(label)}
                        className={`flex items-center justify-between px-3 py-2 rounded-xl border ${cfg.badge} border-transparent hover:opacity-80 transition-all`}>
                        <span className="text-[10px] font-semibold">{label}</span>
                        <span className="text-[10px] font-bold">{count}</span>
                      </button>
                    )
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>

      {/* Compose modal */}
      <AnimatePresence>
        {composeOpen && (
          <ComposeModal
            onClose={() => setComposeOpen(false)}
            onSent={() => { fetchEmails(); setActiveTab('draft_ready') }}
          />
        )}
      </AnimatePresence>

    </motion.div>
  )
}

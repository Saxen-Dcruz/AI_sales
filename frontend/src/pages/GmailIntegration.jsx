import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Archive,
  CheckCircle,
  ChevronRight,
  Inbox,
  Mail, MailOpen,
  RefreshCw, Search,
  Send,
  Star, Tag,
  Users,
  X, Zap
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ApproveDraftService, DiscardDraftService, GenerateDraftService, GetEmailByIdService, GetGmailMessagesService, ResolveEmailService, ResolveEmailGapService, SendEmailService, SyncGmailService, GetEmailAccountsService } from '../services/ApiService'
import GapResolveForm from '../components/GapResolveForm'

// ─── Account color palette — cycles through these for each connected account ─
const ACCOUNT_COLORS = [
  { bg: 'bg-violet-100', text: 'text-violet-700', dot: 'bg-violet-500', pill: 'bg-violet-100 text-violet-700 border-violet-200' },
  { bg: 'bg-sky-100',    text: 'text-sky-700',    dot: 'bg-sky-500',    pill: 'bg-sky-100 text-sky-700 border-sky-200'    },
  { bg: 'bg-rose-100',   text: 'text-rose-700',   dot: 'bg-rose-500',   pill: 'bg-rose-100 text-rose-700 border-rose-200'   },
  { bg: 'bg-amber-100',  text: 'text-amber-700',  dot: 'bg-amber-500',  pill: 'bg-amber-100 text-amber-700 border-amber-200'  },
]

// ─── Config ──────────────────────────────────────────────────────────────────

const LABEL_CONFIG = {
  Sales:         { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-l-emerald-500', dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700', avatar: 'bg-emerald-500' },
  Support:       { bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-l-blue-500',    dot: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700',    avatar: 'bg-blue-500' },
  Grievance:     { bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-l-red-600',     dot: 'bg-red-600',     badge: 'bg-red-100 text-red-700',     avatar: 'bg-red-600' },
  Transactional: { bg: 'bg-gray-50',    text: 'text-gray-600',    border: 'border-l-gray-400',    dot: 'bg-gray-400',    badge: 'bg-gray-100 text-gray-600',    avatar: 'bg-gray-400' },
  Promotional:   { bg: 'bg-purple-50',  text: 'text-purple-700',  border: 'border-l-purple-400',  dot: 'bg-purple-400',  badge: 'bg-purple-100 text-purple-700',  avatar: 'bg-purple-400' },
  Personal:      { bg: 'bg-pink-50',    text: 'text-pink-700',    border: 'border-l-pink-400',    dot: 'bg-pink-400',    badge: 'bg-pink-100 text-pink-700',    avatar: 'bg-pink-400' },
  Unclassified:  { bg: 'bg-gray-50',    text: 'text-gray-500',    border: 'border-l-gray-300',    dot: 'bg-gray-300',    badge: 'bg-gray-100 text-gray-500',    avatar: 'bg-gray-300' },
}

const STATUS_CONFIG = {
  new:           { icon: Mail,         color: 'text-blue-500',    label: 'New' },
  classified:    { icon: Tag,          color: 'text-gray-400',    label: 'Classified' },
  draft_ready:   { icon: Star,         color: 'text-amber-500',   label: 'Draft Ready' },
  pending_human: { icon: AlertCircle,  color: 'text-red-500',     label: 'Needs Review' },
  replied:       { icon: CheckCircle,  color: 'text-emerald-500', label: 'Replied' },
  archived:      { icon: Archive,      color: 'text-gray-400',    label: 'Archived' },
  ignored:       { icon: X,            color: 'text-gray-300',    label: 'Ignored' },
}

const TABS = [
  { key: '',             label: 'Inbox',       icon: Mail,        businessOnly: true  },
  { key: 'Sales',        label: 'Sales',       icon: Zap,         businessOnly: true  },
  { key: 'Support',      label: 'Support',     icon: Users,       businessOnly: true  },
  { key: 'Grievance',    label: 'Grievance',   icon: AlertCircle, businessOnly: true  },
  { key: 'needs_human',  label: 'Needs Review',icon: AlertCircle, businessOnly: true  },
  { key: 'draft_ready',  label: 'Drafts',      icon: Star,        businessOnly: true  },
  { key: 'other',        label: 'Other',       icon: Archive,     businessOnly: false },
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

function EmailRow({ email, selected, onClick, accountColorMap = {} }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const statusCfg = STATUS_CONFIG[email.status] || STATUS_CONFIG.classified
  const StatusIcon = statusCfg.icon
  const isUnread = email.status === 'new'
  const isGrievance = email.label === 'Grievance'
  const unresolvedGaps = (email.followup_gaps || []).filter(g => !(typeof g === 'object' ? g.resolved : false)).length
  const acctColor = email.account_email ? accountColorMap[email.account_email] : null

  // For replied emails show when it was sent (updated_at ≈ reply time); otherwise show received time
  const displayTime = email.status === 'replied' && email.updated_at
    ? relTime(email.updated_at)
    : relTime(email.received_at)
  const timeLabel = email.status === 'replied' ? 'Sent' : 'Rcvd'

  return (
    <button onClick={onClick}
      className={`w-full text-left border-l-4 px-4 py-3 transition-all
        ${selected ? 'bg-blue-50 border-l-blue-500' : `hover:bg-gray-50/80 ${labelCfg.border}`}
        ${isGrievance && !email.resolved_at ? 'bg-red-50/20' : ''}
        border-b border-gray-100 last:border-b-0`}>
      <div className="flex items-center gap-2.5">
        {/* Avatar */}
        <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white ${labelCfg.avatar}`}>
          {senderInitial(email.sender)}
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className={`text-xs truncate ${isUnread ? 'font-bold text-gray-900' : 'font-medium text-gray-700'}`}>
              {senderName(email.sender)}
            </span>
            <span className="text-[9px] text-gray-400 flex-shrink-0 tabular-nums">
              {timeLabel} {displayTime}
            </span>
          </div>
          {/* Subject */}
          <p className={`text-[11px] truncate ${isUnread ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
            {email.subject || '(no subject)'}
          </p>
          {/* Bottom row: badges */}
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${labelCfg.badge}`}>
              {email.label || 'Unclassified'}
            </span>
            {isGrievance && !email.resolved_at && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-red-100 text-red-600">
                ⚠ Urgent
              </span>
            )}
            {email.status === 'draft_ready' && !email.needs_human && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-600">
                Draft
              </span>
            )}
            {email.status === 'draft_ready' && email.needs_human && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-600">
                Review Draft
              </span>
            )}
            {unresolvedGaps > 0 && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                {unresolvedGaps} gap{unresolvedGaps > 1 ? 's' : ''}
              </span>
            )}
            {email.status === 'replied' && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                ✓ Sent
              </span>
            )}
            {/* Account pill — always shown, color-coded per account */}
            {email.account_email && acctColor && (
              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full border flex-shrink-0 flex items-center gap-0.5 ${acctColor.pill}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${acctColor.dot} inline-block`}></span>
                {email.account_email}
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

function EmailDetail({ email, onRefresh, accountColorMap = {} }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const acctColor = email.account_email ? accountColorMap[email.account_email] : null
  const [acting, setActing] = useState(null)
  const [activeGapIndex, setActiveGapIndex] = useState(null)  // which gap form is open
  const [gapResolving, setGapResolving] = useState(false)
  const [note, setNote] = useState('')
  const [done, setDone] = useState(false)
  const [editDraftBody, setEditDraftBody] = useState(email.ai_draft || '')

  const isHumanDraft = (email.label === 'Grievance' || email.label === 'Support') && email.status === 'draft_ready'

  const handleApprove = () => {
    setActing('approve')
    const payload = isHumanDraft && editDraftBody !== email.ai_draft ? { edit_body: editDraftBody } : {}
    ApproveDraftService(email.id, payload,
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
        {/* From / Date / Account */}
        <div className="mt-3 text-xs text-gray-500 space-y-0.5">
          <p><span className="font-medium">From:</span> {email.sender}</p>
          {email.received_at && (
            <p><span className="font-medium">Date:</span> {new Date(email.received_at).toLocaleString()}</p>
          )}
          {email.account_email && (
            <p className="flex items-center gap-1.5">
              <span className="font-medium">Received by:</span>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border flex items-center gap-1
                ${acctColor ? `${acctColor.bg} ${acctColor.text} border-transparent` : 'bg-blue-50 text-blue-600 border-blue-100'}`}>
                {acctColor && <span className={`w-2 h-2 rounded-full ${acctColor.dot}`}></span>}
                {email.account_email}
              </span>
            </p>
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

        {/* AI Draft — editable for Grievance/Support, read-only for Sales */}
        {email.ai_draft && (
          isHumanDraft ? (
            <div className="rounded-xl border border-red-200 bg-red-50/40 p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-semibold text-red-600 uppercase tracking-wide">Draft Reply — Edit before sending</p>
                <span className="text-[9px] bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-semibold">Not sent yet</span>
              </div>
              <textarea
                value={editDraftBody}
                onChange={e => setEditDraftBody(e.target.value)}
                className="w-full text-xs text-gray-700 leading-relaxed border border-red-200 rounded-lg p-3 resize-none focus:outline-none focus:border-red-400 transition-all bg-white"
                rows={10}
              />
            </div>
          ) : (
            <div className={`rounded-xl border p-4 ${LABEL_CONFIG.Sales.bg} border-emerald-200`}>
              <p className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wide mb-2">AI Draft Reply</p>
              <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{email.ai_draft}</p>
            </div>
          )
        )}

        {/* Knowledge Gaps — inline fill form when draft is ready */}
        {email.followup_gaps?.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-amber-600 uppercase tracking-wide mb-2">
              Knowledge Gaps ({email.followup_gaps.filter(g => typeof g === 'object' ? !g.resolved : true).length} unresolved)
            </p>
            <div className="space-y-2">
              {email.followup_gaps.map((gap, i) => {
                const gapObj  = typeof gap === 'string' ? { question: gap, topic: 'general' } : gap
                const resolved = gapObj.resolved
                const isOpen   = activeGapIndex === i

                return (
                  <div key={i} className={`rounded-xl border text-xs transition-all
                    ${resolved
                      ? 'bg-emerald-50 border-emerald-200'
                      : isOpen
                        ? 'bg-white border-indigo-300 shadow-sm'
                        : 'bg-amber-50 border-amber-200'}`}>

                    {/* Gap header row */}
                    <div className="flex items-start gap-2 p-2.5">
                      {resolved
                        ? <CheckCircle size={13} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                        : <AlertCircle size={13} className="text-amber-500 mt-0.5 flex-shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium leading-snug ${resolved ? 'text-emerald-700' : 'text-amber-800'}`}>
                          {gapObj.question}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                          {gapObj.topic && gapObj.topic !== 'general' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 font-semibold uppercase">
                              {gapObj.topic}
                            </span>
                          )}
                          {gapObj.product_name && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">
                              {gapObj.product_name}
                            </span>
                          )}
                          {resolved && gapObj.answer && (
                            <span className="text-[9px] text-emerald-600 italic truncate max-w-[200px]">
                              "{gapObj.answer}"
                            </span>
                          )}
                        </div>
                      </div>
                      {/* Fill / collapse button — only when draft exists */}
                      {!resolved && email.status === 'draft_ready' && (
                        <button
                          onClick={() => setActiveGapIndex(isOpen ? null : i)}
                          className={`flex-shrink-0 text-[10px] font-semibold px-2.5 py-1 rounded-lg transition-all
                            ${isOpen
                              ? 'bg-gray-100 text-gray-600'
                              : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}>
                          {isOpen ? 'Cancel' : 'Fill Gap'}
                        </button>
                      )}
                    </div>

                    {/* Inline resolve form */}
                    {isOpen && !resolved && (
                      <div className="border-t border-indigo-200 px-3 pb-3 pt-2.5">
                        <GapResolveForm
                          gap={gapObj}
                          loading={gapResolving}
                          onCancel={() => setActiveGapIndex(null)}
                          onResolve={(answer, category, productId) => {
                            setGapResolving(true)
                            ResolveEmailGapService(
                              email.id, i, answer, category, productId,
                              () => { setGapResolving(false); setActiveGapIndex(null); onRefresh() },
                              (_s, err) => { setGapResolving(false); alert('Failed: ' + err) }
                            )
                          }}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Resolution note — only for pending_human (not draft_ready, draft is editable above) */}
        {(email.label === 'Grievance' || email.label === 'Support') &&
          email.status === 'pending_human' && !email.resolved_at && (
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

          {/* Grievance / Support — editable draft ready to send */}
          {isHumanDraft && (
            <>
              <button onClick={handleApprove} disabled={acting === 'approve'}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-red-600 text-white text-xs font-semibold hover:bg-red-700 transition-all disabled:opacity-60">
                <Send size={12} />
                {acting === 'approve' ? 'Sending...' : 'Send Reply'}
              </button>
              <button onClick={handleResolve} disabled={acting === 'resolve'}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-gray-100 text-gray-600 text-xs font-medium hover:bg-gray-200 transition-all disabled:opacity-60">
                <CheckCircle size={12} />
                {acting === 'resolve' ? 'Resolving...' : 'Resolve Without Reply'}
              </button>
            </>
          )}

          {/* Sales draft ready */}
          {!isHumanDraft && email.status === 'draft_ready' && email.ai_draft && (
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

          {/* Pending human (fallback state when draft creation failed) */}
          {(email.label === 'Support' || email.label === 'Grievance') &&
            email.status === 'pending_human' && !email.resolved_at && (
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
  const [context, setContext] = useState('')       // customer context fed to AI
  const [body, setBody] = useState('')             // editable email body
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [aiGenerated, setAiGenerated] = useState(false)
  const [contextOpen, setContextOpen] = useState(true)

  const handleGenerate = () => {
    if (!to || !subject) return
    setGenerating(true)
    GenerateDraftService({ to, subject, body: context },
      (data) => {
        setBody(data.draft)
        setAiGenerated(true)
        setContextOpen(false)   // collapse context after generation
        setGenerating(false)
      },
      (_s, err) => { alert('Draft generation failed: ' + err); setGenerating(false) }
    )
  }

  const handleRegenerate = () => {
    setContextOpen(true)
    setAiGenerated(false)
    handleGenerate()
  }

  const handleSend = () => {
    if (!to || !subject || !body) return
    setSending(true)
    SendEmailService({ to, subject, body },
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
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl z-10 overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-50">
              <Send size={15} className="text-blue-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900">New Email</h2>
              <p className="text-[10px] text-gray-400">
                {aiGenerated ? 'AI draft loaded — edit directly below' : 'Add context and generate an AI draft'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 transition-all">
            <X size={15} />
          </button>
        </div>

        <div className="p-6 space-y-3 overflow-y-auto flex-1">
          {/* To + Subject */}
          <div className="space-y-2">
            <div className="flex items-center gap-3 border-b border-gray-100 pb-2">
              <span className="text-xs font-semibold text-gray-400 w-14 flex-shrink-0">To</span>
              <input value={to} onChange={e => setTo(e.target.value)} type="email"
                placeholder="customer@example.com"
                className="flex-1 text-sm text-gray-800 focus:outline-none" />
            </div>
            <div className="flex items-center gap-3 border-b border-gray-100 pb-2">
              <span className="text-xs font-semibold text-gray-400 w-14 flex-shrink-0">Subject</span>
              <input value={subject} onChange={e => setSubject(e.target.value)}
                placeholder="Re: Product Inquiry"
                className="flex-1 text-sm text-gray-800 focus:outline-none" />
            </div>
          </div>

          {/* Context for AI — collapsible */}
          <div className="rounded-xl border border-gray-200 overflow-hidden">
            <button
              onClick={() => setContextOpen(o => !o)}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-all">
              <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                Context for AI {aiGenerated && '(used for generation)'}
              </span>
              <span className="text-[10px] text-gray-400">{contextOpen ? '▲' : '▼'}</span>
            </button>
            <AnimatePresence>
              {contextOpen && (
                <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
                  className="overflow-hidden">
                  <textarea value={context} onChange={e => setContext(e.target.value)} rows={3}
                    placeholder="Paste the customer's question or describe what the email is about…"
                    className="w-full text-sm text-gray-700 px-4 py-3 resize-none focus:outline-none border-t border-gray-100" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Main email body — always visible, editable */}
          <div className="relative">
            {aiGenerated && (
              <div className="absolute top-2 right-2 flex items-center gap-1.5 z-10">
                <span className="text-[9px] font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  AI Draft
                </span>
                <button onClick={handleRegenerate} disabled={generating}
                  className="text-[9px] font-semibold text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full hover:bg-blue-100 transition-all disabled:opacity-50">
                  {generating ? 'Generating…' : 'Regenerate'}
                </button>
              </div>
            )}
            <textarea
              value={body}
              onChange={e => { setBody(e.target.value); setAiGenerated(false) }}
              rows={aiGenerated ? 12 : 8}
              placeholder={aiGenerated ? '' : 'Write your email here, or use "Generate AI Draft" to auto-fill…'}
              className={`w-full text-sm text-gray-800 border rounded-xl px-4 py-3 resize-none focus:outline-none transition-all ${
                aiGenerated
                  ? 'border-emerald-200 bg-emerald-50/30 focus:border-emerald-400 focus:bg-white'
                  : 'border-gray-200 focus:border-blue-400'
              }`}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/60 flex-shrink-0">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700 transition-colors">
            Discard
          </button>
          <div className="flex items-center gap-2">
            {!aiGenerated && (
              <button onClick={handleGenerate} disabled={!to || !subject || generating}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 text-sm font-semibold hover:bg-blue-100 transition-all disabled:opacity-50">
                <Zap size={13} className={generating ? 'animate-pulse' : ''} />
                {generating ? 'Generating…' : 'Generate AI Draft'}
              </button>
            )}
            <button onClick={handleSend} disabled={!to || !subject || !body || sending}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition-all disabled:opacity-50">
              <Send size={13} />
              {sending ? 'Sending…' : 'Send'}
            </button>
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
  // const [syncing, setSyncing] = useState(false)
  const [activeTab, setActiveTab] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [directEmail, setDirectEmail] = useState(null)
  const [composeOpen, setComposeOpen] = useState(false)
  const [accounts, setAccounts] = useState([])
  const [activeAccount, setActiveAccount] = useState('') // '' = all accounts
  // accountColorMap: email_address → ACCOUNT_COLORS[i]
  const [accountColorMap, setAccountColorMap] = useState({})

  useQueryClient()

  const syncMutation = useMutation({
    mutationFn: () => new Promise((resolve, reject) => {
      SyncGmailService(
        resolve,
        (_s, err) => reject(new Error(err))
      )
    }),
    onSuccess: () => {
      fetchEmails()
    }
  })

  // When navigated from GapsPage with a specific email to show
  useEffect(() => {
    const emailId = location.state?.selectEmailId
    if (!emailId) return
    GetEmailByIdService(emailId,
      (data) => { setDirectEmail(data); setSelected(data.id) },
      () => { }
    )
  }, [location.state])

  // Load accounts on mount and build color map
  useEffect(() => {
    GetEmailAccountsService(
      (data) => {
        const items = data?.items || []
        setAccounts(items)
        // Assign a stable color to each account by index
        const colorMap = {}
        items.forEach((a, i) => {
          colorMap[a.email_address] = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length]
        })
        setAccountColorMap(colorMap)
      },
      () => {}
    )
  }, [])

  const fetchEmails = useCallback(() => {
    setLoading(true)
    const tab = TABS.find(t => t.key === activeTab) || TABS[0]
    const params = { page, limit: PAGE_SIZE }
    if (activeTab === 'needs_human') params.needs_human = true
    else if (activeTab === 'draft_ready') params.status = 'draft_ready'
    else if (activeTab === 'other') {
      // Other tab: show noise emails (Promotional/Transactional/Personal/Unclassified)
      params.business_only = false
    } else if (activeTab) {
      params.label = activeTab
    }
    // For business tabs keep business_only default (true). For 'other' explicitly false.
    if (activeTab !== 'other') params.business_only = true
    if (activeAccount) params.account_id = activeAccount

    GetGmailMessagesService(params,
      (data) => { setEmails(data?.items || []); setTotal(data?.total || 0); setLoading(false) },
      () => setLoading(false)
    )
  }, [page, activeTab, activeAccount])

  useEffect(() => { fetchEmails() }, [fetchEmails])
  useEffect(() => { setPage(1); setSelected(null) }, [activeTab])
  useEffect(() => { setPage(1); setSelected(null) }, [activeAccount])

  const handleSync = () => {
    syncMutation.mutate()
  }

  // 3. Smart Background Sync Polling (Every 60s & on Window Focus)
  useQuery({
    queryKey: ['backgroundSync'],
    queryFn: () => new Promise((resolve, reject) => {
      SyncGmailService(
        () => {
          fetchEmails()
          resolve(true)
        },
        (_s, err) => reject(new Error(err))
      )
    }),
    refetchInterval: 60000,
    refetchOnWindowFocus: true,
  })

  useEffect(() => { setPage(1); setSelected(null) }, [search])

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
          <p className="text-xs text-gray-400">
            {total} emails · auto-classified by AI
            {activeAccount && <span className="ml-1 text-blue-500">· {activeAccount}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
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

          {/* Account selector pills — shown when multiple accounts */}
          {accounts.length > 1 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => { setActiveAccount(''); setPage(1); setSelected(null) }}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all
                  ${!activeAccount ? 'bg-gray-800 text-white shadow-sm' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                <Inbox size={11} />
                All
              </button>
              {accounts.map((a, i) => {
                const color = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length]
                const isActive = activeAccount === a.id
                return (
                  <button key={a.id}
                    onClick={() => { setActiveAccount(a.id); setPage(1); setSelected(null) }}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all border
                      ${isActive ? `${color.bg} ${color.text} border-transparent shadow-sm` : 'bg-white text-gray-600 hover:bg-gray-50 border-gray-200'}`}>
                    <span className={`w-2 h-2 rounded-full ${color.dot}`}></span>
                    {a.email_address.split('@')[0]}
                    {a.is_primary && <span className="text-[8px] opacity-60">★</span>}
                  </button>
                )
              })}
            </div>
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
                      accountColorMap={accountColorMap}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>

          {/* Pagination — always visible */}
          <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 bg-gray-50/50 flex-shrink-0">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 transition-all disabled:opacity-30 disabled:cursor-not-allowed">
              ← Prev
            </button>
            <span className="text-[10px] text-gray-500 font-medium">
              {total === 0 ? '0 emails' : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`}
            </span>
            <button
              disabled={page >= Math.ceil(total / PAGE_SIZE) || total === 0}
              onClick={() => setPage(p => p + 1)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 transition-all disabled:opacity-30 disabled:cursor-not-allowed">
              Next →
            </button>
          </div>
        </div>

        {/* Right: detail */}
        <div className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            {selectedEmail ? (
              <motion.div key={selectedEmail.id} className="h-full"
                initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); setSelected(null) }} accountColorMap={accountColorMap} />
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

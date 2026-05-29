import { Float, MeshDistortMaterial, Sphere } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Archive,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Inbox,
  Mail, MailOpen,
  RefreshCw, Reply, Search,
  Send,
  ShieldAlert,
  Star, Tag,
  Users,
  X, Zap
} from 'lucide-react'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ApproveDraftService, DiscardDraftService, GenerateDraftService, GetEmailByIdService, GetGmailMessagesService, GetGmailThreadService, ResolveEmailService, ResolveEmailGapService, SendEmailService, SyncGmailService, GetEmailAccountsService } from '../services/ApiService'
import GapResolveForm from '../components/GapResolveForm'

// ─── Account color palette — cycles through these for each connected account ─
const ACCOUNT_COLORS = [
  { bg: 'bg-violet-100', text: 'text-violet-700', dot: 'bg-violet-500', pill: 'bg-violet-100 text-violet-700 border-violet-200' },
  { bg: 'bg-sky-100',    text: 'text-sky-700',    dot: 'bg-sky-500',    pill: 'bg-sky-100 text-sky-700 border-sky-200'    },
  { bg: 'bg-rose-100',   text: 'text-rose-700',   dot: 'bg-rose-500',   pill: 'bg-rose-100 text-rose-700 border-rose-200'   },
  { bg: 'bg-amber-100',  text: 'text-amber-700',  dot: 'bg-amber-500',  pill: 'bg-amber-100 text-amber-700 border-amber-200'  },
]

// ─── Config & Colors ─────────────────────────────────────────────────────────
const COLORS = {
  indigo: '#4f46e5',
  violet: '#8b5cf6',
  emerald: '#10b981',
  amber: '#f59e0b',
  rose: '#f43f5e',
  slate: '#94a3b8',
}

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

// ─── 3D Aura Component ──────────────────────────────────────────────────────
function AuraSphere3D({ size = 400 }) {
  return (
    <div className="pointer-events-none opacity-60 z-0" style={{ width: size, height: size }}>
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.5} />
          <pointLight position={[10, 10, 10]} intensity={1} />
          <Float speed={2} rotationIntensity={1} floatIntensity={2}>
            <Sphere args={[1.5, 64, 64]}>
              <MeshDistortMaterial color={COLORS.indigo} speed={3} distort={0.4} roughness={0.2} metalness={0.8} transparent opacity={0.6} />
            </Sphere>
          </Float>
        </Suspense>
      </Canvas>
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/20 to-violet-500/20 blur-[100px] rounded-full" />
    </div>
  )
}

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

function senderEmail(sender) {
  if (!sender) return ''
  const match = sender.match(/<([^>]+)>/)
  return (match ? match[1] : sender).trim()
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
      className={`w-full text-left border-l-4 px-4 py-3.5 transition-all
        ${selected ? 'bg-blue-50 border-l-blue-500' : `hover:bg-gray-50/80 ${labelCfg.border}`}
        ${isGrievance && !email.resolved_at ? 'bg-red-50/20' : ''}
        border-b border-gray-100 last:border-b-0`}>
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className={`w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold text-white ${labelCfg.avatar}`}>
          {senderInitial(email.sender)}
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className={`text-sm truncate ${isUnread ? 'font-bold text-gray-900' : 'font-semibold text-gray-700'}`}>
              {senderName(email.sender)}
            </span>
            <span className="text-[10px] text-gray-400 flex-shrink-0 tabular-nums">
              {timeLabel} {displayTime}
            </span>
          </div>

          {/* Subject */}
          <p className={`text-xs truncate ${isUnread ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
            {email.subject || '(no subject)'}
          </p>
          {/* Bottom row: badges */}
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${labelCfg.badge}`}>
              {email.label || 'Unclassified'}
            </span>
            {email.thread_count > 1 && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 flex items-center gap-0.5"
                title={`${email.thread_count} messages in this thread`}>
                💬 {email.thread_count}
              </span>
            )}
            {isGrievance && !email.resolved_at && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-red-100 text-red-600">
                ⚠ Urgent
              </span>
            )}
            {email.status === 'draft_ready' && !email.needs_human && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-600">
                Draft
              </span>
            )}
            {email.status === 'draft_ready' && email.needs_human && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-600">
                Review Draft
              </span>
            )}
            {unresolvedGaps > 0 && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                {unresolvedGaps} gap{unresolvedGaps > 1 ? 's' : ''}
              </span>
            )}
            {email.status === 'replied' && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                ✓ Sent
              </span>
            )}
            {/* Account pill — always shown, color-coded per account */}
            {email.account_email && acctColor && (
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border flex-shrink-0 flex items-center gap-0.5 ${acctColor.pill}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${acctColor.dot} inline-block`}></span>
                {email.account_email}
              </span>
            )}
            <StatusIcon size={10} className={`${statusCfg.color} ml-auto flex-shrink-0`} />
          </div>
        </div>

        <ChevronRight size={14} className={`flex-shrink-0 transition-transform ${selected ? 'text-indigo-600 translate-x-1' : 'text-slate-300'}`} />
      </div>
    </button>
  )
}

// ─── Email detail ─────────────────────────────────────────────────────────────

function EmailDetail({ email, onRefresh, accountColorMap = {} }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const acctColor = email.account_email ? accountColorMap[email.account_email] : null
  const [acting, setActing] = useState(null)
  const [activeGapIndex, setActiveGapIndex] = useState(null)
  const [gapResolving, setGapResolving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [note, setNote] = useState('')
  const [done, setDone] = useState(false)
  const [editDraftBody, setEditDraftBody] = useState(email.ai_draft || '')
  // Manual threaded reply composer
  const [replyOpen, setReplyOpen] = useState(false)
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')
  const [replySending, setReplySending] = useState(false)
  // Thread conversation: all messages in the same gmail_thread_id (chronological)
  const [threadMessages, setThreadMessages] = useState([])

  // Fetch the full thread when the selected email changes
  useEffect(() => {
    if (!email.gmail_thread_id) {
      setThreadMessages([email])
      return
    }
    GetGmailThreadService(email.gmail_thread_id,
      (data) => setThreadMessages(data?.items || [email]),
      () => setThreadMessages([email])
    )
  }, [email.gmail_thread_id, email.id])

  // The latest message in the thread — that's the one we act on (approve/send/etc)
  const latestMessage = threadMessages.length > 1
    ? threadMessages[threadMessages.length - 1]
    : email

  // Reset draft body when the email changes (e.g. after gap-fill regeneration loads a new draft)
  useEffect(() => {
    setEditDraftBody(email.ai_draft || '')
  }, [email.id, email.ai_draft])

  // Reset the reply composer whenever a different email is opened
  useEffect(() => {
    setReplyOpen(false)
    setReplyBody('')
    const subj = email.subject || ''
    setReplySubject(subj.startsWith('Re:') ? subj : `Re: ${subj}`)
  }, [email.id, email.subject])

  const handleSendReply = () => {
    if (!replyBody.trim()) return
    setReplySending(true)
    SendEmailService(
      {
        to: senderEmail(email.sender),
        subject: replySubject.trim() || 'Re:',
        body: replyBody,
        thread_id: email.gmail_thread_id || null,
        account_id: email.account_id || null,
        reply_to_email_id: email.id,
      },
      () => { setReplySending(false); setReplyOpen(false); setReplyBody(''); setDone(true); setTimeout(onRefresh, 800) },
      (_s, err) => { setReplySending(false); alert('Failed to send: ' + err) }
    )
  }

  const isHumanDraft = (email.label === 'Grievance' || email.label === 'Support') && email.status === 'draft_ready'

  const handleApprove = () => {
    setActing('approve')
    // Always send edited body if user changed it — works for all draft labels
    const payload = editDraftBody !== email.ai_draft ? { edit_body: editDraftBody } : {}
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
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center p-12">
        <div className="w-16 h-16 rounded-3xl bg-emerald-50 flex items-center justify-center text-emerald-500 shadow-xl shadow-emerald-100">
          <CheckCircle size={32} />
        </div>
        <div className="space-y-1">
          <p className="text-lg font-black text-slate-900">Intelligence Deployed</p>
          <p className="text-sm font-bold text-slate-400">Refreshing your inbox flow...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className={`px-8 py-6 border-b border-slate-100 relative overflow-hidden`}>
        <div className={`absolute top-0 left-0 w-1 h-full bg-gradient-to-b`} style={{ background: labelCfg.color }} />

        <div className="flex items-start justify-between gap-6 relative z-10">
          <div className="flex-1 min-w-0">
            <h2 className="text-3xl font-black text-slate-900 leading-tight mb-2">{email.subject || '(no subject)'}</h2>
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-sm font-black px-3 py-1.5 rounded-xl uppercase tracking-wider ${labelCfg.badge}`}>
                {email.label}
              </span>
              {email.needs_human && (
                <span className="text-sm font-black px-3 py-1.5 rounded-xl bg-rose-100 text-rose-600 uppercase tracking-wider">
                  Needs Review
                </span>
              )}
              {email.classifier_confidence && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 text-sm font-bold text-slate-500 uppercase tracking-wider">
                  <Zap size={14} className="text-amber-500" />
                  {typeof email.classifier_confidence === 'number'
                    ? `${Math.round(email.classifier_confidence * 100)}% accuracy`
                    : `${email.classifier_confidence} accuracy`}
                </div>
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

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-8">

        {/* Classifier reasoning */}
        {email.classifier_reasoning && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100/50">
            <div className="flex items-center gap-3 mb-4">
              <Cpu size={18} className="text-indigo-600" />
              <p className="text-sm font-black text-indigo-600 uppercase tracking-[0.2em]">Intelligence Insight</p>
            </div>
            <p className="text-base font-bold text-slate-700 leading-relaxed">{email.classifier_reasoning}</p>
          </motion.div>
        )}

        {/* Conversation timeline — chat-style: customer → AI reply → customer → AI reply */}
        {threadMessages.length > 0 && (() => {
          // Build a chronological list of bubbles.
          // Each inbound email row produces 1 or 2 bubbles:
          //   1) the customer's message (left, white)
          //   2) the AI's reply (right, emerald) if ai_draft is set
          //      — labeled "Sent" if status=replied, "Draft" if status=draft_ready
          const bubbles = []
          for (const m of threadMessages) {
            if (m.direction === 'outbound') {
              // Standalone outbound row (rare — usually drafts are on the inbound row)
              bubbles.push({
                key: `${m.id}-out`, side: 'right', kind: 'sent',
                sender: 'You', body: m.body_text, time: m.received_at,
              })
              continue
            }
            // Inbound message
            bubbles.push({
              key: `${m.id}-in`, side: 'left', kind: 'inbound',
              sender: senderName(m.sender || ''), body: m.body_text, time: m.received_at,
            })
            // AI draft / reply attached to this inbound
            if (m.ai_draft) {
              const kind = m.status === 'replied' ? 'sent' : 'draft'
              bubbles.push({
                key: `${m.id}-draft`, side: 'right', kind,
                sender: kind === 'sent' ? 'You (auto-sent)' : 'Draft (pending approval)',
                body: m.ai_draft,
                time: m.updated_at || m.received_at,
              })
            }
          }
          // No global sort: threadMessages is already chronological (server orders
          // by received_at asc) and each AI reply is pushed immediately after the
          // inbound it answers — so a draft always stays adjacent to its parent
          // message. A time-based sort would regroup drafts when timestamps are
          // close, which is the "all messages grouped" bug we are avoiding.

          return (
            <div>
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Conversation
                {threadMessages.length > 1 && <span className="ml-1 text-indigo-500">({threadMessages.length} messages)</span>}
              </p>
              <div className="space-y-2 max-h-[28rem] overflow-y-auto pr-1">
                {bubbles.map(b => {
                  const styles =
                    b.side === 'right'
                      ? b.kind === 'draft'
                        ? 'bg-amber-50/70 border-amber-200 ml-8'
                        : 'bg-emerald-50/60 border-emerald-200 ml-8'
                      : 'bg-white border-gray-200 mr-8'
                  const labelClr =
                    b.side === 'right'
                      ? b.kind === 'draft' ? 'text-amber-700' : 'text-emerald-700'
                      : 'text-gray-700'
                  return (
                    <div key={b.key} className={`rounded-xl p-3 border ${styles}`}>
                      <div className="flex items-center justify-between mb-1.5 gap-2">
                        <span className={`text-[10px] font-semibold ${labelClr}`}>
                          {b.kind === 'draft' && '✋ '}
                          {b.kind === 'sent' && '✓ '}
                          {b.sender}
                        </span>
                        <span className="text-[10px] text-gray-400 whitespace-nowrap">
                          {b.time ? new Date(b.time).toLocaleString() : ''}
                        </span>
                      </div>
                      <div className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
                        {b.body || '(no content)'}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })()}

        {/* AI Draft — editable action area, shown only when a reply is still pending approval.
            Already-sent drafts are rendered in the conversation timeline above (no duplicate box). */}
        {email.ai_draft && email.status === 'draft_ready' && (
          <div className={`rounded-xl border p-4 ${isHumanDraft ? 'border-red-200 bg-red-50/40' : 'border-emerald-200 bg-emerald-50/40'}`}>
            <div className="flex items-center justify-between mb-2">
              <p className={`text-[10px] font-semibold uppercase tracking-wide ${isHumanDraft ? 'text-red-600' : 'text-emerald-600'}`}>
                AI Draft Reply — Edit before sending
              </p>
              <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${isHumanDraft ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-700'}`}>
                Not sent yet
              </span>
            </div>
            <textarea
              value={editDraftBody}
              onChange={e => setEditDraftBody(e.target.value)}
              className={`w-full text-xs text-gray-700 leading-relaxed border rounded-lg p-3 resize-none focus:outline-none transition-all bg-white
                ${isHumanDraft ? 'border-red-200 focus:border-red-400' : 'border-emerald-200 focus:border-emerald-400'}`}
              rows={10}
            />
            {editDraftBody !== email.ai_draft && (
              <p className="text-[10px] text-gray-500 mt-1.5 italic">You've edited the draft — your changes will be sent on approve.</p>
            )}
          </div>
        ) : null}

        {/* Regenerating draft spinner */}
        {regenerating && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-indigo-50 border border-indigo-200">
            <RefreshCw size={16} className="text-indigo-500 animate-spin flex-shrink-0" />
            <div>
              <p className="text-xs font-semibold text-indigo-700">Regenerating draft with complete knowledge…</p>
              <p className="text-[10px] text-indigo-500 mt-0.5">Re-running RAG pipeline with all gap answers added to knowledge base</p>
            </div>
          </div>
        )}

        {/* Knowledge Gaps — inline fill form when draft is ready */}
        {!regenerating && email.followup_gaps?.length > 0 && (
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
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500 font-semibold uppercase">
                              {gapObj.topic}
                            </span>
                          )}
                          {gapObj.product_name && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">
                              {gapObj.product_name}
                            </span>
                          )}
                          {resolved && gapObj.answer && (
                            <span className="text-[10px] text-emerald-600 italic truncate max-w-[200px]">
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
                          loading={gapResolving || regenerating}
                          onCancel={() => setActiveGapIndex(null)}
                          onResolve={(answer, category, productId) => {
                            setGapResolving(true)
                            // Check if this is the LAST unresolved gap
                            const unresolvedAfter = email.followup_gaps.filter(
                              (g, idx) => idx !== i && typeof g === 'object' && !g.resolved
                            ).length
                            const isLastGap = unresolvedAfter === 0
                            ResolveEmailGapService(
                              email.id, i, answer, category, productId,
                              () => {
                                setGapResolving(false)
                                setActiveGapIndex(null)
                                if (isLastGap) {
                                  // All gaps filled — backend will regenerate the draft.
                                  // Show spinner while waiting for regeneration to complete.
                                  setRegenerating(true)
                                  setTimeout(() => {
                                    setRegenerating(false)
                                    onRefresh()
                                  }, 4000)  // give backend ~4s to finish RAG + draft generation
                                } else {
                                  onRefresh()
                                }
                              },
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
              placeholder="Detail the resolution steps taken..."
              className="w-full text-sm font-bold text-slate-700 border border-slate-200 rounded-2xl p-4 resize-none h-28 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 transition-all placeholder:text-slate-300" />
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
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl bg-emerald-600 text-white text-sm font-bold hover:bg-emerald-700 transition-all disabled:opacity-60 shadow-lg shadow-emerald-200">
                <Send size={16} />
                {acting === 'approve' ? 'Sending...' : 'Approve & Send'}
              </button>
              <button onClick={handleDiscard} disabled={acting === 'discard'}
                className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-white border border-slate-200 text-slate-600 text-sm font-bold hover:bg-slate-50 transition-all disabled:opacity-60 shadow-sm">
                <X size={16} />
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
            <div className="flex items-center gap-2 text-sm text-emerald-600 font-bold bg-emerald-50 px-4 py-2 rounded-xl">
              <CheckCircle size={18} /> Replied
            </div>
          )}
          {email.resolved_at && (
            <div className="flex items-center gap-2 text-sm text-slate-600 font-bold bg-slate-100 px-4 py-2 rounded-xl">
              <CheckCircle size={18} className="text-emerald-500" />
              Resolved by {email.resolved_by} · {relTime(email.resolved_at)}
            </div>
          )}

          {/* Manual threaded reply — available for any email with a sender */}
          {!replyOpen && (
            <button onClick={() => setReplyOpen(true)}
              className="ml-auto flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-all">
              <Reply size={13} />
              Reply
            </button>
          )}
        </div>

        {/* Gmail-style reply composer */}
        {replyOpen && (
          <div className="mt-3 rounded-xl border border-gray-200 bg-white overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50">
              <span className="text-xs font-semibold text-gray-600">Reply</span>
              <button onClick={() => { setReplyOpen(false); setReplyBody('') }}
                className="text-gray-400 hover:text-gray-600 transition-colors">
                <X size={15} />
              </button>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100">
              <span className="text-xs text-gray-400 w-14 flex-shrink-0">To</span>
              <span className="text-xs text-gray-700 truncate">{senderEmail(email.sender)}</span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100">
              <span className="text-xs text-gray-400 w-14 flex-shrink-0">Subject</span>
              <input value={replySubject} onChange={e => setReplySubject(e.target.value)}
                className="flex-1 text-xs text-gray-800 focus:outline-none bg-transparent" />
            </div>
            <textarea value={replyBody} onChange={e => setReplyBody(e.target.value)}
              placeholder="Type your message here..."
              rows={8}
              className="w-full text-xs text-gray-700 leading-relaxed p-4 resize-none focus:outline-none" />
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/60">
              <span className="text-[10px] text-gray-400">
                {email.account_email ? `Sending from ${email.account_email}` : 'Sending from default account'}
              </span>
              <div className="flex items-center gap-2">
                <button onClick={() => { setReplyOpen(false); setReplyBody('') }}
                  className="px-3 py-2 rounded-xl bg-gray-100 text-gray-600 text-xs font-medium hover:bg-gray-200 transition-all">
                  Cancel
                </button>
                <button onClick={handleSendReply} disabled={replySending || !replyBody.trim()}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all disabled:opacity-50">
                  <Send size={12} />
                  {replySending ? 'Sending...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        )}
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
              <Zap size={15} className="text-blue-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900">Compose with AI</h2>
              <p className="text-[10px] text-gray-400">
                {aiGenerated ? 'AI draft loaded — edit directly below' : 'Add context and generate an AI draft'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-200 text-gray-400 transition-all">
            <X size={20} />
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
                <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                  AI Draft
                </span>
                <button onClick={handleRegenerate} disabled={generating}
                  className="text-[10px] font-semibold text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full hover:bg-blue-100 transition-all disabled:opacity-50">
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
  // Global counts independent of current tab/filter — always accurate
  const [globalNeedsReview, setGlobalNeedsReview] = useState(0)
  const [globalDraftReady, setGlobalDraftReady] = useState(0)

  useQueryClient()

  const syncMutation = useMutation({
    mutationFn: () => new Promise((resolve, reject) => {
      SyncGmailService(
        resolve,
        (_s, err) => reject(new Error(err))
      )
    }),
    onSuccess: () => { fetchEmails(); fetchAnalytics() }
  })

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

  // Fetch global counts (needs_human + draft_ready) independently of current tab
  // so the badges are always accurate regardless of what tab is active.
  const fetchGlobalCounts = useCallback(() => {
    const acctParam = activeAccount ? `&account_id=${activeAccount}` : ''
    GetGmailMessagesService({ needs_human: true, limit: 1, business_only: true, ...(activeAccount ? { account_id: activeAccount } : {}) },
      (d) => setGlobalNeedsReview(d?.total || 0), () => {})
    GetGmailMessagesService({ status: 'draft_ready', limit: 1, business_only: true, ...(activeAccount ? { account_id: activeAccount } : {}) },
      (d) => setGlobalDraftReady(d?.total || 0), () => {})
  }, [activeAccount])

  const fetchEmails = useCallback(() => {
    setLoading(true)
    const tab = TABS.find(t => t.key === activeTab) || TABS[0]
    const params = { page, limit: PAGE_SIZE }
    if (activeTab === 'needs_human') params.needs_human = true
    else if (activeTab === 'draft_ready') params.status = 'draft_ready'
    else if (activeTab === 'other') {
      params.business_only = false
    } else if (activeTab) {
      params.label = activeTab
    }
    if (activeTab !== 'other') params.business_only = true
    if (activeAccount) params.account_id = activeAccount

    GetGmailMessagesService(params,
      (data) => {
        setEmails(data?.items || [])
        setTotal(data?.total || 0)
        setLoading(false)
        fetchGlobalCounts()  // always refresh badge counts after loading emails
      },
      () => setLoading(false)
    )
  }, [page, activeTab, activeAccount])

  useEffect(() => { fetchEmails() }, [fetchEmails])
  useEffect(() => { fetchGlobalCounts() }, [fetchGlobalCounts])
  useEffect(() => { setPage(1); setSelected(null) }, [activeTab])
  useEffect(() => { setPage(1); setSelected(null) }, [activeAccount])

  const handleSync = () => syncMutation.mutate()

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

  const syncing = syncMutation.isPending

  const searched = search
    ? emails.filter(e =>
      (e.subject || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.sender || '').toLowerCase().includes(search.toLowerCase())
    )
    : emails

  // Thread grouping is done server-side (one row per gmail_thread_id, latest
  // message, with thread_count). Here we just keep the server order, but apply
  // local search filtering on top.
  const filtered = searched

  // directEmail is set when navigated from GapsPage — may not be in the current paginated list
  const selectedEmail = selected
    ? (directEmail?.id === selected ? directEmail : emails.find(e => e.id === selected))
    : null

  // Use global counts (not filtered to current page/tab) so badges are always accurate
  const needsReview = globalNeedsReview
  const draftReady = globalDraftReady

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-[#fcf8ff] text-slate-900 px-6 py-4 md:px-10 md:py-6 relative overflow-hidden font-sans">

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
          {/* Compose is for a NEW email — hidden while reading a thread (use Reply instead) */}
          {!selectedEmail && (
            <button onClick={() => setComposeOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all">
              <Zap size={13} />
              Compose with AI
            </button>
          )}
        </div>
      </div>

      {/* Main two-panel layout */}
      <div className="flex gap-0 glass-card overflow-hidden" style={{ height: '84vh' }}>

        {/* Left: list */}
        <div className="w-[26rem] flex-shrink-0 flex flex-col border-r border-gray-100">
          {/* Tabs */}
          <div className="overflow-x-auto border-b border-gray-100">
            <div className="flex min-w-max">
              {TABS.map(tab => {
                const Icon = tab.icon
                return (
                  <button key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-1.5 px-4 py-3 text-xs font-semibold border-b-2 transition-all whitespace-nowrap
                      ${activeTab === tab.key
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-400 hover:text-gray-600'}`}>
                    <Icon size={13} />
                    {tab.label}
                  </button>
                )
              })}
            </div>
            <h1 className="text-4xl font-black tracking-tight text-slate-900">
              Intelligence <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-500">Inbox</span>
            </h1>
            <p className="text-slate-500 font-bold text-base">Managing AI-driven interactions across all connected identities.</p>
          </div>

          {/* Search */}
          <div className="px-3 py-2.5 border-b border-gray-100">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search emails..."
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-blue-400 transition-all" />
            </div>
          </div>

                {acctDropdownOpen && (
                  <div className="absolute top-full right-0 mt-2 w-64 bg-white/90 backdrop-blur-xl border border-slate-100 rounded-2xl shadow-xl z-50 overflow-hidden">
                    <button onClick={() => { setActiveAccount(''); setPage(1); setSelected(null); setAcctDropdownOpen(false) }}
                      className={`w-full flex items-center gap-2 px-5 py-3 text-sm font-black uppercase tracking-wider transition-all hover:bg-slate-50
                        ${!activeAccount ? 'text-indigo-600 bg-indigo-50/50' : 'text-slate-500'}`}>
                      <Inbox size={14} /> All Accounts
                    </button>
                    {accounts.map((a, i) => {
                      const color = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length]
                      const isActive = activeAccount === a.id
                      return (
                        <button key={a.id} onClick={() => { setActiveAccount(a.id); setPage(1); setSelected(null); setAcctDropdownOpen(false) }}
                          className={`w-full flex items-center gap-2 px-5 py-3 text-sm font-black transition-all hover:bg-slate-50 border-t border-slate-50
                            ${isActive ? 'text-indigo-600 bg-indigo-50/50' : 'text-slate-500'}`}>
                          <span className={`w-2.5 h-2.5 rounded-full ${color.dot}`}></span>
                          <span className="truncate">{a.email_address}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
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

          {/* Pagination — always visible */}
          <div className="flex items-center justify-between px-3 py-2.5 border-t border-gray-100 bg-gray-50/50 flex-shrink-0">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-semibold bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 transition-all disabled:opacity-30 disabled:cursor-not-allowed">
              ← Prev
            </button>
            <span className="text-xs text-gray-500 font-medium">
              {total === 0 ? '0 emails' : `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} of ${total}`}
            </span>
            <button
              disabled={page >= Math.ceil(total / PAGE_SIZE) || total === 0}
              onClick={() => setPage(p => p + 1)}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-semibold bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 transition-all disabled:opacity-30 disabled:cursor-not-allowed">
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
                <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); fetchGlobalCounts(); setSelected(null) }} accountColorMap={accountColorMap} />
              </motion.div>
            ) : (
              <motion.div key="empty" className="flex flex-col items-center justify-center h-full gap-4 text-center p-10"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="w-20 h-20 rounded-full bg-gray-50 flex items-center justify-center">
                  <MailOpen size={44} className="text-gray-300" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-500">Select an email to read</p>
                  <p className="text-sm text-gray-400 mt-1">Pick a conversation from the list to view the full thread and AI drafts.</p>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-3 w-full max-w-md">
                  {Object.entries(LABEL_CONFIG).filter(([k]) => k !== 'Unclassified').map(([label, cfg]) => {
                    const count = emails.filter(e => e.label === label).length
                    if (!count) return null
                    return (
                      <button key={label} onClick={() => setActiveTab(label)}
                        className={`flex items-center justify-between px-4 py-3 rounded-xl border ${cfg.badge} border-transparent hover:opacity-80 transition-all`}>
                        <span className="text-sm font-semibold">{label}</span>
                        <span className="text-sm font-bold">{count}</span>
                      </button>
                    )
                  })}
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4 text-center px-6">
                  <div className="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-300 shadow-inner">
                    <MailOpen size={32} />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-900 uppercase tracking-wider">No Signals</p>
                    <p className="text-sm font-bold text-slate-400 mt-2">Try adjusting your filters or active account</p>
                  </div>
                </div>
              ) : (
                <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }} className="divide-y divide-slate-100">
                  {threadedList.map(({ latest, emails: tEmails }) => (
                    <motion.div key={latest.id} variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}>
                      <EmailRow email={latest} count={tEmails.length} selected={selected === latest.id} onClick={() => setSelected(selected === latest.id ? null : latest.id)} accountColorMap={accountColorMap} />
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-8 py-5 border-t border-slate-100 bg-white/60 backdrop-blur-sm">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 transition-colors">
                <ChevronRight size={18} className="rotate-180" /> Prev
              </button>
              <div className="flex items-center gap-3">
                <span className="text-sm font-black text-slate-900">{page}</span>
                <span className="text-sm font-bold text-slate-300">/</span>
                <span className="text-sm font-black text-slate-400">{Math.ceil(total / PAGE_SIZE) || 1}</span>
              </div>
              <button disabled={page >= Math.ceil(total / PAGE_SIZE) || Math.ceil(total / PAGE_SIZE) === 0} onClick={() => setPage(p => p + 1)} className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 transition-colors">
                Next <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {/* Right Panel: Detail View */}
          <div className="flex-1 min-w-0 bg-white/90 backdrop-blur-xl">
            <AnimatePresence mode="wait">
              {selectedEmail ? (
                <motion.div key={selectedEmail.id} className="h-full" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                  <EmailDetail email={selectedEmail} threadEmails={selectedThread?.emails} onRefresh={() => { fetchEmails(); setSelected(null) }} accountColorMap={accountColorMap} />
                </motion.div>
              ) : (
                <motion.div key="empty" className="flex flex-col items-center justify-center h-full gap-5 text-center p-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="w-24 h-24 rounded-full bg-slate-50 flex items-center justify-center border-4 border-white shadow-xl shadow-slate-100">
                    <MailOpen size={40} className="text-indigo-200" />
                  </div>
                  <p className="text-lg font-black text-slate-500 uppercase tracking-widest">Awaiting Selection</p>
                  <div className="mt-6 grid grid-cols-2 gap-4 w-full max-w-md">
                    {Object.entries(LABEL_CONFIG).filter(([k]) => k !== 'Unclassified').map(([label, cfg]) => {
                      const count = emails.filter(e => e.label === label).length
                      if (!count) return null
                      return (
                        <button key={label} onClick={() => setActiveTab(label)} className={`flex items-center justify-between px-5 py-4 rounded-2xl border ${cfg.badge} border-transparent hover:shadow-lg hover:scale-[1.02] transition-all`}>
                          <span className="text-sm font-black uppercase tracking-wider">{label}</span>
                          <span className="text-sm font-black">{count}</span>
                        </button>
                      )
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Compose Modal */}
        <AnimatePresence>
          {composeOpen && <ComposeModal onClose={() => setComposeOpen(false)} onSent={() => { fetchEmails(); setActiveTab('draft_ready') }} />}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
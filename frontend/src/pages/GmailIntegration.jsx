import ApplicationStore from '../utils/ApplicationStore'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Archive,
  Briefcase,
  Building2,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Filter,
  Inbox,
  Mail,
  MailOpen,
  Phone,
  RefreshCw,
  Reply,
  Search,
  Send,
  Star,
  Tag,
  Target,
  TrendingUp,
  Users,
  X,
  Zap,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ApproveDraftService, DiscardDraftService, GenerateDraftService, GetEmailByIdService, GetEmailCrmContextService, GetGmailMessagesService, GetGmailThreadService, MarkEmailReadService, ResolveEmailService, ResolveEmailGapService, SendEmailService, SyncGmailService, GetEmailAccountsService, ListUsersService, UpdateLeadService, UpdateDealService, GetEmailTemplatesService, CreateEmailTemplateService, DeleteEmailTemplateService } from '../services/ApiService'
import GapResolveForm from '../components/GapResolveForm'

// ─── Account color palette — cycles through these for each connected account ─
const ACCOUNT_COLORS = [
  { bg: 'bg-violet-100', text: 'text-violet-700', dot: 'bg-violet-500', pill: 'bg-violet-100 text-violet-700 border-violet-200' },
  { bg: 'bg-sky-100',    text: 'text-sky-700',    dot: 'bg-sky-500',    pill: 'bg-sky-100 text-sky-700 border-sky-200'    },
  { bg: 'bg-rose-100',   text: 'text-rose-700',   dot: 'bg-rose-500',   pill: 'bg-rose-100 text-rose-700 border-rose-200'   },
  { bg: 'bg-amber-100',  text: 'text-amber-700',  dot: 'bg-amber-500',  pill: 'bg-amber-100 text-amber-700 border-amber-200'  },
]

// ─── Account selector dropdown ───────────────────────────────────────────────
function AccountDropdown({ accounts, activeAccount, onSelect }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  const current = accounts.find(a => a.id === activeAccount)
  const currentIdx = accounts.findIndex(a => a.id === activeAccount)
  const currentColor = currentIdx >= 0 ? ACCOUNT_COLORS[currentIdx % ACCOUNT_COLORS.length] : null

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-medium transition-all border
          ${activeAccount ? 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50' : 'bg-gray-800 text-white border-transparent shadow-sm'}`}>
        {current ? (
          <>
            <span className={`w-2 h-2 rounded-full ${currentColor.dot}`}></span>
            {current.email_address.split('@')[0]}
            {current.is_primary && <span className="text-[8px] opacity-60">★</span>}
          </>
        ) : (
          <>
            <Inbox size={11} />
            All accounts
          </>
        )}
        <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 mt-1.5 w-52 z-50 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden py-1">
            <button
              onClick={() => { onSelect(''); setOpen(false) }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-left transition-colors
                ${!activeAccount ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'}`}>
              <Inbox size={12} />
              All accounts
            </button>
            {accounts.map((a, i) => {
              const color = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length]
              const isActive = activeAccount === a.id
              return (
                <button key={a.id}
                  onClick={() => { onSelect(a.id); setOpen(false) }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-left transition-colors
                    ${isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-600 hover:bg-gray-50'}`}>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${color.dot}`}></span>
                  <span className="truncate">{a.email_address}</span>
                  {a.is_primary && <span className="text-[9px] opacity-60 ml-auto flex-shrink-0">★</span>}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

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
  // Business pipeline labels
  { key: '',               label: 'Inbox',          icon: Mail,        businessOnly: true,  color: '#6172f3' },
  { key: 'Sales',          label: 'Sales',           icon: Zap,         businessOnly: true,  color: '#10b981' },
  { key: 'Support',        label: 'Support',         icon: Users,       businessOnly: true,  color: '#3b82f6' },
  { key: 'Grievance',      label: 'Grievance',       icon: AlertCircle, businessOnly: true,  color: '#ef4444' },
  { key: 'needs_human',    label: 'Needs Review',    icon: AlertCircle, businessOnly: true,  color: '#f59e0b' },
  { key: 'draft_ready',    label: 'Drafts',          icon: Star,        businessOnly: true,  color: '#f59e0b' },
  // Non-business labels (individual)
  { key: 'Transactional',  label: 'Transactional',   icon: Archive,     businessOnly: false, color: '#f97316' },
  { key: 'Promotional',    label: 'Promotional',     icon: Tag,         businessOnly: false, color: '#8b5cf6' },
  { key: 'Personal',       label: 'Personal',        icon: Users,       businessOnly: false, color: '#ec4899' },
  { key: 'Unclassified',   label: 'Unclassified',    icon: Mail,        businessOnly: false, color: '#9ca3af' },
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

function senderEmail(sender) {
  if (!sender) return ''
  const match = sender.match(/<([^>]+)>/)
  return (match ? match[1] : sender).trim()
}

// ─── Email row ───────────────────────────────────────────────────────────────

function EmailRow({ email, selected, onClick, accountColorMap = {}, acctOwnerMap = {} }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const statusCfg = STATUS_CONFIG[email.status] || STATUS_CONFIG.classified
  const StatusIcon = statusCfg.icon
  // "Unread" = a human hasn't opened this email yet in the dashboard. Independent of
  // `status` (AI pipeline progress) — the row un-bolds as soon as it's viewed.
  const isUnread = !email.is_read
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
            {email.status === 'replied' && !email.opened_at && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                ✓ Sent
              </span>
            )}
            {email.opened_at && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-200 text-emerald-800">
                ✓ Opened{email.open_count > 1 ? ` ×${email.open_count}` : ''}
              </span>
            )}
            {/* Account pill — color-coded per account + owner name for super-admin */}
            {email.account_email && acctColor && (
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border flex-shrink-0 flex items-center gap-0.5 ${acctColor.pill}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${acctColor.dot} inline-block`}></span>
                {email.account_email}
                {acctOwnerMap[email.account_email] && (
                  <span className="ml-0.5 opacity-70">({acctOwnerMap[email.account_email].split('@')[0]})</span>
                )}
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
  const [replyTemplates, setReplyTemplates] = useState([])
  const [showReplyTemplates, setShowReplyTemplates] = useState(false)

  useEffect(() => {
    GetEmailTemplatesService(
      (data) => setReplyTemplates(data?.items || []),
      () => {}
    )
  }, [])
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
    // Use the latest *inbound* message in the thread for In-Reply-To so Gmail
    // threads it correctly. If the last message is outbound (a bot reply), walk
    // back to find the most recent inbound. Fallback to the inbox email itself.
    const latestInbound = [...threadMessages].reverse().find(m => m.direction === 'inbound') || email
    SendEmailService(
      {
        to: senderEmail(latestInbound.sender || email.sender),
        subject: replySubject.trim() || 'Re:',
        body: replyBody,
        thread_id: email.gmail_thread_id || null,
        account_id: email.account_id || null,
        reply_to_email_id: latestInbound.id,
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
                openedAt: m.opened_at, openCount: m.open_count || 0,
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
                        <span className={`text-[10px] font-semibold ${labelClr} flex items-center gap-1.5`}>
                          {b.kind === 'draft' && '✋ '}
                          {b.kind === 'sent' && '✓ '}
                          {b.sender}
                          {b.kind === 'sent' && b.openedAt && (
                            <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 ml-1">
                              Opened {b.openCount > 1 ? `×${b.openCount}` : ''}
                            </span>
                          )}
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
        )}

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
                      {/* Fill / collapse button — the backend always accepts a gap answer
                          (it embeds it into the knowledge base regardless of email status;
                          draft regeneration is simply skipped when there's no draft to redo) */}
                      {!resolved && (
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
                                if (isLastGap && email.gmail_draft_id) {
                                  // All gaps filled and a draft still exists — backend regenerates
                                  // it (RAG + LLM). Poll every 2s until the draft_id or status
                                  // changes, so we never show a stale or broken state.
                                  // (If the draft was discarded there's nothing to regenerate —
                                  // just refresh immediately, see the else branch below.)
                                  setRegenerating(true)
                                  let attempts = 0
                                  const poll = () => {
                                    attempts++
                                    GetEmailByIdService(email.id,
                                      (fresh) => {
                                        const draftChanged = fresh.gmail_draft_id !== email.gmail_draft_id
                                        const doneWaiting = draftChanged || attempts >= 15
                                        if (doneWaiting) {
                                          setRegenerating(false)
                                          onRefresh()
                                        } else {
                                          setTimeout(poll, 2000)
                                        }
                                      },
                                      () => { setRegenerating(false); onRefresh() }
                                    )
                                  }
                                  setTimeout(poll, 2000)
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
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-600">Reply</span>
                <div className="relative">
                  <button onClick={() => setShowReplyTemplates(s => !s)}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold text-gray-500 hover:bg-gray-200 transition-all">
                    <FileText size={11} /> Templates
                  </button>
                  {showReplyTemplates && (
                    <div className="absolute top-full mt-1 left-0 z-20 bg-white rounded-xl border border-gray-100 shadow-xl min-w-[180px] max-h-48 overflow-y-auto">
                      {replyTemplates.length === 0 ? (
                        <p className="text-xs text-gray-400 px-4 py-3">No templates yet.</p>
                      ) : replyTemplates.map(tpl => (
                        <button key={tpl.id} onClick={() => { if (!replyBody) setReplyBody(tpl.body); setShowReplyTemplates(false) }}
                          className="w-full text-left px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                          <p className="text-xs font-semibold text-gray-800">{tpl.name}</p>
                          <p className="text-[10px] text-gray-400 truncate">{tpl.subject}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
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

// ─── CRM record panel ─────────────────────────────────────────────────────────
// A compact "record" sidebar next to the email, in the spirit of the contact/
// deal panels in Attio, Odoo CRM and FreshBooks — shows the linked contact,
// company, lead status, classification and any associated deal/PO, all pulled
// live from /gmail/{id}/crm (no hardcoded data).

const LEAD_STATUS_OPTIONS = ['Uncontacted', 'Contacted', 'Engaged', 'PO Raised', 'Converted', 'Lost']
const DEAL_STAGE_OPTIONS = ['Prospect', 'Contacted', 'Qualified', 'PO Raised', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost']

const CLASSIFICATION_BADGE = {
  HIGH:   'bg-emerald-100 text-emerald-700',
  MEDIUM: 'bg-amber-100 text-amber-700',
  LOW:    'bg-rose-100 text-rose-700',
}

function initials(name) {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || '?'
}

function CrmPanel({ email, onSelectEmail, onClose }) {
  const [crm, setCrm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [savingStatus, setSavingStatus] = useState(false)
  const [savingStage, setSavingStage] = useState(false)
  const [activity, setActivity] = useState([])

  useEffect(() => {
    setLoading(true)
    setCrm(null)
    setActivity([])
    GetEmailCrmContextService(email.id,
      (data) => {
        setCrm(data)
        setLoading(false)
        if (data?.lead?.id) {
          GetGmailMessagesService({ lead_id: data.lead.id, limit: 8, page: 1, business_only: false },
            (res) => setActivity((res?.items || []).filter(e => e.id !== email.id)),
            () => {}
          )
        }
      },
      () => { setCrm(null); setLoading(false) }
    )
  }, [email.id])

  const handleStatusChange = (newStatus) => {
    if (!crm?.lead) return
    setSavingStatus(true)
    UpdateLeadService(crm.lead.id, { status: newStatus },
      () => { setCrm({ ...crm, lead: { ...crm.lead, status: newStatus } }); setSavingStatus(false) },
      (_s, err) => { setSavingStatus(false); alert('Failed to update status: ' + err) }
    )
  }

  const handleStageChange = (newStage) => {
    if (!crm?.deal) return
    setSavingStage(true)
    UpdateDealService(crm.deal.id, { stage: newStage },
      () => { setCrm({ ...crm, deal: { ...crm.deal, stage: newStage } }); setSavingStage(false) },
      (_s, err) => { setSavingStage(false); alert('Failed to update stage: ' + err) }
    )
  }

  return (
    <div className="w-80 flex-shrink-0 border-l border-gray-100 bg-white h-full overflow-y-auto">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between sticky top-0 bg-white z-10">
        <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">CRM Record</p>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
            <X size={15} />
          </button>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-10 text-gray-400 text-xs">Loading...</div>
      ) : !crm?.lead ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 px-4 text-center">
          <Users size={22} className="text-gray-200" />
          <p className="text-xs text-gray-400">No CRM contact linked to this email yet.</p>
        </div>
      ) : (
        <div className="p-4 space-y-4">

          {/* Contact card */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold flex-shrink-0">
                {initials(crm.lead.name)}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-bold text-gray-900 truncate">{crm.lead.name || 'Unknown contact'}</p>
                {crm.lead.email && <p className="text-[11px] text-gray-400 truncate">{crm.lead.email}</p>}
              </div>
            </div>

            <div className="mt-3 space-y-1.5">
              {crm.lead.company_name && (
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <Building2 size={12} className="text-gray-400" />
                  {crm.lead.company_name}
                </div>
              )}
              {crm.lead.phone && (
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <Phone size={12} className="text-gray-400" />
                  {crm.lead.phone}
                </div>
              )}
              {crm.lead.classification && (
                <div className="flex items-center gap-2">
                  <Target size={12} className="text-gray-400" />
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${CLASSIFICATION_BADGE[crm.lead.classification] || 'bg-gray-100 text-gray-500'}`}>
                    {crm.lead.classification} priority
                  </span>
                </div>
              )}
            </div>

            {/* Status */}
            <div className="mt-3">
              <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Status</label>
              <select value={crm.lead.status} disabled={savingStatus}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="mt-1 w-full text-xs font-semibold text-gray-700 border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-blue-400 disabled:opacity-50">
                {LEAD_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                {!LEAD_STATUS_OPTIONS.includes(crm.lead.status) && (
                  <option value={crm.lead.status}>{crm.lead.status}</option>
                )}
              </select>
            </div>

            {/* Engagement score */}
            <div className="mt-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Engagement</span>
                <span className="text-[10px] font-bold text-gray-600">{crm.lead.engagement_score}/100</span>
              </div>
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(100, crm.lead.engagement_score)}%` }} />
              </div>
            </div>

            {crm.lead.next_best_action && (
              <div className="mt-3 p-2.5 rounded-lg bg-blue-50 border border-blue-100">
                <p className="text-[10px] font-semibold text-blue-600 uppercase tracking-wide mb-0.5">Next Best Action</p>
                <p className="text-xs text-blue-700 leading-snug">{crm.lead.next_best_action}</p>
              </div>
            )}

            {crm.lead.last_contacted_at && (
              <p className="mt-2 text-[10px] text-gray-400">
                Last contacted {new Date(crm.lead.last_contacted_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Deal / PO card */}
          {crm.deal ? (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
              <div className="flex items-center gap-2 mb-2">
                <Briefcase size={13} className="text-violet-500" />
                <p className="text-sm font-bold text-gray-900 truncate">{crm.deal.deal_name}</p>
              </div>

              <div className="flex items-center justify-between text-xs text-gray-600 mb-3">
                <span className="flex items-center gap-1"><TrendingUp size={12} className="text-emerald-500" />Value</span>
                <span className="font-bold text-gray-900">${Number(crm.deal.deal_value).toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between text-xs text-gray-600 mb-3">
                <span>Win Probability</span>
                <span className="font-bold text-gray-900">{crm.deal.win_probability}%</span>
              </div>
              {crm.deal.expected_close_date && (
                <div className="flex items-center justify-between text-xs text-gray-600 mb-3">
                  <span>Expected Close</span>
                  <span className="font-medium text-gray-700">{new Date(crm.deal.expected_close_date).toLocaleDateString()}</span>
                </div>
              )}

              <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Deal Stage</label>
              <select value={crm.deal.stage} disabled={savingStage}
                onChange={(e) => handleStageChange(e.target.value)}
                className="mt-1 w-full text-xs font-semibold text-gray-700 border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-violet-400 disabled:opacity-50">
                {DEAL_STAGE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                {!DEAL_STAGE_OPTIONS.includes(crm.deal.stage) && (
                  <option value={crm.deal.stage}>{crm.deal.stage}</option>
                )}
              </select>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
              <Briefcase size={18} className="text-gray-200 mx-auto mb-1.5" />
              <p className="text-xs text-gray-400">No deal/PO opened for this contact yet.</p>
            </div>
          )}

          {/* Activity timeline */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
            <div className="flex items-center gap-2 mb-3">
              <Clock size={13} className="text-gray-400" />
              <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Recent Activity</p>
            </div>
            {activity.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-2">No other conversations yet.</p>
            ) : (
              <div className="space-y-2">
                {activity.map(e => {
                  const cfg = LABEL_CONFIG[e.label] || LABEL_CONFIG.Unclassified
                  const isOut = e.direction === 'outbound'
                  return (
                    <button key={e.id} onClick={() => onSelectEmail && onSelectEmail(e.id)}
                      className="w-full text-left p-2 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${isOut ? 'bg-emerald-400' : 'bg-blue-400'}`} />
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-medium text-gray-800 truncate">{e.subject || '(no subject)'}</p>
                          <div className="flex items-center gap-1 mt-0.5">
                            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${cfg.badge}`}>{e.label}</span>
                            {e.direction === 'outbound' && e.opened_at && (
                              <span className="text-[9px] text-emerald-600 font-semibold">✓ Opened</span>
                            )}
                            <span className="text-[9px] text-gray-400 ml-auto">{relTime(e.received_at)}</span>
                          </div>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
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
  const [templates, setTemplates] = useState([])
  const [showTemplates, setShowTemplates] = useState(false)
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)

  useEffect(() => {
    GetEmailTemplatesService(
      (data) => setTemplates(data?.items || []),
      () => {}
    )
  }, [])

  const applyTemplate = (tpl) => {
    if (!subject) setSubject(tpl.subject)
    if (!body) setBody(tpl.body)
    setShowTemplates(false)
  }

  const saveAsTemplate = () => {
    if (!templateName.trim() || !subject || !body) return
    setSavingTemplate(true)
    CreateEmailTemplateService({ name: templateName.trim(), subject, body },
      (tpl) => {
        setTemplates(t => [...t, tpl])
        setShowSaveTemplate(false)
        setTemplateName('')
        setSavingTemplate(false)
      },
      () => { setSavingTemplate(false); alert('Failed to save template') }
    )
  }

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

          {/* Templates row */}
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative">
              <button onClick={() => setShowTemplates(s => !s)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-all">
                <FileText size={12} />
                Templates {templates.length > 0 ? `(${templates.length})` : ''}
              </button>
              {showTemplates && templates.length > 0 && (
                <div className="absolute top-full mt-1 left-0 z-20 bg-white rounded-xl border border-gray-100 shadow-xl min-w-[200px] max-h-52 overflow-y-auto">
                  {templates.map(tpl => (
                    <button key={tpl.id} onClick={() => applyTemplate(tpl)}
                      className="w-full text-left px-4 py-2.5 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                      <p className="text-xs font-semibold text-gray-800">{tpl.name}</p>
                      <p className="text-[10px] text-gray-400 truncate">{tpl.subject}</p>
                    </button>
                  ))}
                </div>
              )}
              {showTemplates && templates.length === 0 && (
                <div className="absolute top-full mt-1 left-0 z-20 bg-white rounded-xl border border-gray-100 shadow-xl px-4 py-3">
                  <p className="text-xs text-gray-400">No templates yet. Save one below.</p>
                </div>
              )}
            </div>
            {body && subject && (
              <button onClick={() => setShowSaveTemplate(s => !s)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-all">
                + Save as template
              </button>
            )}
            {showSaveTemplate && (
              <div className="flex items-center gap-1.5">
                <input value={templateName} onChange={e => setTemplateName(e.target.value)}
                  placeholder="Template name"
                  className="text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-400" />
                <button onClick={saveAsTemplate} disabled={savingTemplate || !templateName.trim()}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 transition-all">
                  {savingTemplate ? 'Saving…' : 'Save'}
                </button>
              </div>
            )}
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
  const [syncing, setSyncing] = useState(false)
  const [activeTab, setActiveTab] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [crmOpen, setCrmOpen] = useState(false)
  const [filterOpen, setFilterOpen] = useState(false)
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [directEmail, setDirectEmail] = useState(null)
  const [composeOpen, setComposeOpen] = useState(false)
  const [accounts, setAccounts] = useState([])
  const [activeAccount, setActiveAccount] = useState('') // '' = all accounts
  // accountColorMap: email_address → ACCOUNT_COLORS[i]
  const [accountColorMap, setAccountColorMap] = useState({})
  // acctOwnerMap: gmail_address → user_email (super-admin only)
  const [acctOwnerMap, setAcctOwnerMap] = useState({})
  // Global counts independent of current tab/filter — always accurate
  const [globalNeedsReview, setGlobalNeedsReview] = useState(0)
  const [globalDraftReady, setGlobalDraftReady] = useState(0)

  // When navigated from GapsPage with a specific email to show
  useEffect(() => {
    const emailId = location.state?.selectEmailId
    if (!emailId) return
    GetEmailByIdService(emailId,
      (data) => {
        setDirectEmail(data)
        setSelected(data.id)
        if (!data.is_read) MarkEmailReadService(data.id, () => {}, () => {})
      },
      () => { }
    )
  }, [location.state])

  // Load accounts on mount and build color map + owner map
  useEffect(() => {
    const { userDetails } = ApplicationStore().getStorage('userDetails') || {}
    const superAdmin = userDetails?.userRole === 'Admin'
    GetEmailAccountsService(
      (data) => {
        const items = data?.items || []
        setAccounts(items)
        const colorMap = {}
        items.forEach((a, i) => {
          colorMap[a.email_address] = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length]
        })
        setAccountColorMap(colorMap)
      },
      () => {}
    )
    // Super-admin: build gmail → owner-user map from the users list
    if (superAdmin) {
      ListUsersService(
        (users) => {
          const ownerMap = {}
          ;(users || []).forEach(u => {
            ;(u.gmail_accounts || []).forEach(a => {
              ownerMap[a.email_address] = u.email
            })
          })
          setAcctOwnerMap(ownerMap)
        },
        () => {}
      )
    }
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
    else {
      const tabCfg = TABS.find(t => t.key === activeTab)
      const isBusinessOnly = tabCfg ? tabCfg.businessOnly : true
      params.business_only = isBusinessOnly
      // For specific non-pipeline labels, pass the label filter explicitly
      if (activeTab && activeTab !== 'other' && !isBusinessOnly) {
        params.label = activeTab
      } else if (activeTab && isBusinessOnly) {
        params.label = activeTab
      }
    }
    if (activeAccount) params.account_id = activeAccount
    if (filterDateFrom) params.date_from = new Date(filterDateFrom).toISOString()
    if (filterDateTo) { const d = new Date(filterDateTo); d.setHours(23,59,59,999); params.date_to = d.toISOString() }
    if (filterStatus) params.status = filterStatus

    GetGmailMessagesService(params,
      (data) => {
        setEmails(data?.items || [])
        setTotal(data?.total || 0)
        setLoading(false)
        fetchGlobalCounts()  // always refresh badge counts after loading emails
      },
      () => setLoading(false)
    )
  }, [page, activeTab, activeAccount, filterDateFrom, filterDateTo, filterStatus])

  useEffect(() => { fetchEmails() }, [fetchEmails])
  useEffect(() => { fetchGlobalCounts() }, [fetchGlobalCounts])
  useEffect(() => { setPage(1); setSelected(null) }, [activeTab])
  useEffect(() => { setPage(1); setSelected(null) }, [activeAccount])

  // Keep latest fetchers in refs so the socket effect below (mount-only) always
  // calls the current versions without needing to reconnect when filters change.
  const fetchEmailsRef = useRef(fetchEmails)
  const fetchGlobalCountsRef = useRef(fetchGlobalCounts)
  useEffect(() => { fetchEmailsRef.current = fetchEmails }, [fetchEmails])
  useEffect(() => { fetchGlobalCountsRef.current = fetchGlobalCounts }, [fetchGlobalCounts])

  // Live updates — the backend pushes a message here the moment the Gmail Pub/Sub
  // webhook processes a new email, so the inbox refreshes instantly instead of
  // waiting for the user to manually sync or reload.
  useEffect(() => {
    const { accessToken } = ApplicationStore().getStorage('userDetails') || {}
    if (!accessToken) return

    let socket
    let reconnectTimer
    let closedByEffect = false
    const wsBase = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws')

    const connect = () => {
      socket = new WebSocket(`${wsBase}gmail/ws?token=${encodeURIComponent(accessToken)}`)
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'new_email') {
            // New mail sorts to the top of page 1 (backend orders unread-first, newest-first) —
            // reset there so it's visible even if the user had paged forward.
            setPage(1)
            fetchEmailsRef.current()
            fetchGlobalCountsRef.current()
          }
        } catch {
          // ignore malformed frames
        }
      }
      socket.onclose = () => {
        if (!closedByEffect) reconnectTimer = setTimeout(connect, 5000)
      }
      socket.onerror = () => socket.close()
    }
    connect()

    return () => {
      closedByEffect = true
      clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [])

  const openEmail = (email) => {
    setCrmOpen(false)
    setSelected(selected === email.id ? null : email.id)
    if (!email.is_read) {
      // Optimistic — un-bold immediately rather than waiting on the round trip.
      setEmails(prev => prev.map(e => e.id === email.id ? { ...e, is_read: true } : e))
      MarkEmailReadService(email.id, () => {}, () => {})
    }
  }

  const handleSync = () => {
    setSyncing(true)
    SyncGmailService(
      () => { setSyncing(false); setTimeout(fetchEmails, 2000) },
      () => setSyncing(false)
    )
  }

  useEffect(() => { setPage(1); setSelected(null) }, [search])

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

          {/* Account selector dropdown — shown when multiple accounts */}
          {accounts.length > 1 && (
            <AccountDropdown
              accounts={accounts}
              activeAccount={activeAccount}
              onSelect={(id) => { setActiveAccount(id); setPage(1); setSelected(null) }}
            />
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
          </div>

          {/* Search */}
          <div className="px-3 py-2.5 border-b border-gray-100 space-y-2">
            <div className="flex items-center gap-1.5">
              <div className="relative flex-1">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search emails..."
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-gray-50 border border-gray-200 text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-blue-400 transition-all" />
              </div>
              <button onClick={() => setFilterOpen(o => !o)}
                className={`flex items-center gap-1 px-2.5 py-2 rounded-lg border text-xs font-semibold transition-all flex-shrink-0
                  ${(filterDateFrom || filterDateTo || filterStatus)
                    ? 'border-blue-400 text-blue-600 bg-blue-50'
                    : 'border-gray-200 text-gray-400 hover:bg-gray-50'}`}>
                <Filter size={12} />
                {(filterDateFrom || filterDateTo || filterStatus) ? 'Filtered' : 'Filter'}
              </button>
            </div>
            {filterOpen && (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center gap-1.5">
                  <input type="date" value={filterDateFrom} onChange={e => { setFilterDateFrom(e.target.value); setPage(1) }}
                    className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-400" />
                  <span className="text-[10px] text-gray-400">to</span>
                  <input type="date" value={filterDateTo} onChange={e => { setFilterDateTo(e.target.value); setPage(1) }}
                    className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-400" />
                </div>
                <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1) }}
                  className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-400 text-gray-600">
                  <option value="">All statuses</option>
                  <option value="new">New</option>
                  <option value="draft_ready">Draft Ready</option>
                  <option value="pending_human">Pending Human</option>
                  <option value="replied">Replied</option>
                  <option value="archived">Archived</option>
                </select>
                {(filterDateFrom || filterDateTo || filterStatus) && (
                  <button onClick={() => { setFilterDateFrom(''); setFilterDateTo(''); setFilterStatus(''); setPage(1) }}
                    className="text-[10px] text-rose-500 hover:text-rose-700 font-semibold">
                    Clear filters
                  </button>
                )}
              </div>
            )}
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
                      onClick={() => openEmail(email)}
                      accountColorMap={accountColorMap}
                      acctOwnerMap={acctOwnerMap}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>

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
        <div className="flex-1 min-w-0 flex">
          <AnimatePresence mode="wait">
            {selectedEmail ? (
              <motion.div key={selectedEmail.id} className="relative h-full flex-1 min-w-0 flex"
                initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                <div className="flex-1 min-w-0">
                  <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); fetchGlobalCounts(); setSelected(null) }} accountColorMap={accountColorMap} acctOwnerMap={acctOwnerMap} />
                </div>

                {/* CRM toggle button — opens the record as a slide-in drawer */}
                {!crmOpen && (
                  <button
                    onClick={() => setCrmOpen(true)}
                    className="absolute top-3 right-3 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-gray-200 shadow-sm text-xs font-semibold text-gray-600 hover:text-blue-600 hover:border-blue-300 transition-colors">
                    <Users size={13} />
                    CRM Record
                  </button>
                )}

                {/* Slide-in CRM drawer (overlays on top, doesn't cramp the reply area) */}
                <AnimatePresence>
                  {crmOpen && (
                    <>
                      <motion.div
                        className="absolute inset-0 z-30 bg-black/20"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        onClick={() => setCrmOpen(false)} />
                      <motion.div
                        className="absolute top-0 right-0 z-40 h-full shadow-2xl"
                        initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
                        transition={{ type: 'tween', duration: 0.22 }}>
                        <CrmPanel
                          email={selectedEmail}
                          onSelectEmail={(id) => { setSelected(id); setCrmOpen(false) }}
                          onClose={() => setCrmOpen(false)} />
                      </motion.div>
                    </>
                  )}
                </AnimatePresence>
              </motion.div>
            ) : (
              <motion.div key="empty" className="flex-1 flex flex-col items-center justify-center h-full gap-4 text-center p-10"
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

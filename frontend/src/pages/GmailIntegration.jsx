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
  Clock,
  Cpu,
  Inbox,
  Mail, MailOpen,
  MessageSquare,
  RefreshCw, Search,
  Send,
  ShieldAlert,
  Star, Tag,
  Users,
  X, Zap
} from 'lucide-react'
import { Suspense, useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import GapResolveForm from '../components/GapResolveForm'
import {
  ApproveDraftService, DiscardDraftService, GenerateDraftService,
  GetEmailAccountsService,
  GetEmailByIdService, GetGmailAnalyticsService, GetGmailMessagesService,
  ResolveEmailGapService,
  ResolveEmailService,
  SendEmailService,
  SyncGmailService
} from '../services/ApiService'

// ─── Account Color Palette ───────────────────────────────────────────────────
const ACCOUNT_COLORS = [
  { bg: 'bg-violet-100', text: 'text-violet-700', dot: 'bg-violet-500', pill: 'bg-violet-50 text-violet-700 border-violet-200' },
  { bg: 'bg-sky-100', text: 'text-sky-700', dot: 'bg-sky-500', pill: 'bg-sky-50 text-sky-700 border-sky-200' },
  { bg: 'bg-rose-100', text: 'text-rose-700', dot: 'bg-rose-500', pill: 'bg-rose-50 text-rose-700 border-rose-200' },
  { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500', pill: 'bg-amber-50 text-amber-700 border-amber-200' },
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
  Sales: { bg: 'bg-indigo-50/50', text: 'text-indigo-700', border: 'border-l-indigo-400', dot: 'bg-indigo-400', badge: 'bg-indigo-100 text-indigo-700', color: COLORS.indigo },
  Support: { bg: 'bg-emerald-50/50', text: 'text-emerald-700', border: 'border-l-emerald-400', dot: 'bg-emerald-400', badge: 'bg-emerald-100 text-emerald-700', color: COLORS.emerald },
  Grievance: { bg: 'bg-rose-50/50', text: 'text-rose-700', border: 'border-l-rose-400', dot: 'bg-rose-400', badge: 'bg-rose-100 text-rose-700', color: COLORS.rose },
  Transactional: { bg: 'bg-violet-50/50', text: 'text-violet-700', border: 'border-l-violet-300', dot: 'bg-violet-300', badge: 'bg-violet-100 text-violet-700', color: COLORS.violet },
  Promotional: { bg: 'bg-amber-50/50', text: 'text-amber-700', border: 'border-l-amber-300', dot: 'bg-amber-300', badge: 'bg-amber-100 text-amber-700', color: COLORS.amber },
  Personal: { bg: 'bg-pink-50/50', text: 'text-pink-700', border: 'border-l-pink-300', dot: 'bg-pink-300', badge: 'bg-pink-100 text-pink-700', color: '#ec4899' },
  Unclassified: { bg: 'bg-slate-50/50', text: 'text-slate-600', border: 'border-l-slate-300', dot: 'bg-slate-300', badge: 'bg-slate-100 text-slate-600', color: COLORS.slate },
}

const STATUS_CONFIG = {
  new: { icon: Mail, color: 'text-indigo-500', label: 'New' },
  classified: { icon: Tag, color: 'text-slate-400', label: 'Classified' },
  draft_ready: { icon: Star, color: 'text-amber-500', label: 'Draft Ready' },
  pending_human: { icon: AlertCircle, color: 'text-rose-500', label: 'Needs Review' },
  replied: { icon: CheckCircle, color: 'text-emerald-500', label: 'Replied' },
  archived: { icon: Archive, color: 'text-slate-400', label: 'Archived' },
  ignored: { icon: X, color: 'text-slate-300', label: 'Ignored' },
}

const TABS = [
  { key: '', label: 'All', icon: MessageSquare, businessOnly: true },
  { key: 'Sales', label: 'Sales', icon: Zap, businessOnly: true },
  { key: 'Support', label: 'Support', icon: Users, businessOnly: true },
  { key: 'Grievance', label: 'Grievance', icon: AlertCircle, businessOnly: true },
  { key: 'Transactional', label: 'Transactional', icon: Send, businessOnly: true },
  { key: 'needs_human', label: 'Needs Review', icon: ShieldAlert, businessOnly: true },
  { key: 'draft_ready', label: 'Drafts', icon: Star, businessOnly: true },
  { key: 'other', label: 'Other', icon: Archive, businessOnly: false },
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

// ─── Email row ───────────────────────────────────────────────────────────────
function EmailRow({ email, selected, onClick, accountColorMap = {} }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const statusCfg = STATUS_CONFIG[email.status] || STATUS_CONFIG.classified
  const StatusIcon = statusCfg.icon
  const isUnread = email.status === 'new'
  const isGrievance = email.label === 'Grievance'
  const unresolvedGaps = (email.followup_gaps || []).filter(g => !(typeof g === 'object' ? g.resolved : false)).length
  const acctColor = email.account_email ? accountColorMap[email.account_email] : null

  const displayTime = email.status === 'replied' && email.updated_at ? relTime(email.updated_at) : relTime(email.received_at)
  const timeLabel = email.status === 'replied' ? 'Sent' : 'Rcvd'

  return (
    <button onClick={onClick}
      className={`w-full text-left border-l-[3px] px-5 py-4 transition-all
        ${selected ? 'bg-indigo-50/50 border-l-indigo-600' : `hover:bg-slate-50/50 ${labelCfg.border}`}
        ${isGrievance && !email.resolved_at ? 'bg-rose-50/20' : ''}
        border-b border-slate-100 last:border-b-0 group`}>

      <div className="flex items-center gap-4">
        {/* Avatar */}
        <div className="relative">
          <div className={`w-10 h-10 rounded-2xl flex-shrink-0 flex items-center justify-center text-sm font-black text-white shadow-sm
            ${email.label === 'Sales' ? 'bg-indigo-600' :
              email.label === 'Support' ? 'bg-emerald-600' :
                email.label === 'Grievance' ? 'bg-rose-600' :
                  email.label === 'Transactional' ? 'bg-violet-500' :
                    'bg-slate-400'}`}>
            {senderInitial(email.sender)}
          </div>
          {isUnread && <div className="absolute -top-1 -right-1 w-3 h-3 bg-indigo-600 rounded-full border-2 border-white" />}
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className={`text-lg truncate tracking-tight ${isUnread ? 'font-extrabold text-slate-900' : 'font-bold text-slate-700'}`}>
              {senderName(email.sender)}
            </span>
            <span className="text-sm font-bold text-slate-400 flex-shrink-0 uppercase tracking-tighter tabular-nums">
              {timeLabel} {displayTime}
            </span>
          </div>

          {/* Subject */}
          <p className={`text-base truncate leading-tight ${isUnread ? 'font-bold text-slate-800' : 'font-semibold text-slate-500'}`}>
            {email.subject || '(no subject)'}
          </p>

          {/* Bottom row: badges */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span className={`text-xs font-black px-2.5 py-1 rounded-lg uppercase tracking-wider ${labelCfg.badge}`}>
              {email.label || 'Unclassified'}
            </span>
            {isGrievance && !email.resolved_at && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-rose-100 text-rose-600 uppercase tracking-wider">
                ⚠ Urgent
              </span>
            )}
            {email.status === 'draft_ready' && !email.needs_human && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-amber-100 text-amber-600 uppercase tracking-wider">
                Draft Ready
              </span>
            )}
            {email.status === 'draft_ready' && email.needs_human && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-orange-100 text-orange-600 uppercase tracking-wider">
                Review Draft
              </span>
            )}
            {unresolvedGaps > 0 && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-amber-100 text-amber-700 uppercase tracking-wider">
                {unresolvedGaps} Gap{unresolvedGaps > 1 ? 's' : ''}
              </span>
            )}
            {email.status === 'replied' && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-700 uppercase tracking-wider">
                ✓ Sent
              </span>
            )}
            {email.account_email && acctColor && (
              <span className={`text-xs font-black px-2.5 py-1 rounded-lg border flex-shrink-0 flex items-center gap-1.5 ${acctColor.pill}`}>
                <span className={`w-2 h-2 rounded-full ${acctColor.dot} inline-block`}></span>
                {email.account_email}
              </span>
            )}

            <div className="ml-auto opacity-40 group-hover:opacity-100 transition-opacity">
              <StatusIcon size={14} className={`${statusCfg.color}`} />
            </div>
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
        <div className="mt-6 flex flex-col sm:flex-row sm:items-center gap-6 text-sm font-bold">
          <div className="flex items-center gap-3 text-slate-500">
            <Users size={18} className="text-indigo-400" />
            <span className="text-slate-400 uppercase tracking-widest text-xs">From:</span>
            <span className="text-slate-900">{email.sender}</span>
          </div>
          <div className="flex items-center gap-3 text-slate-500 sm:ml-auto">
            <Clock size={18} className="text-violet-400" />
            <span className="text-slate-400 uppercase tracking-widest text-xs">Date:</span>
            <span className="text-slate-900">{new Date(email.received_at).toLocaleString()}</span>
          </div>
          {email.account_email && (
            <div className="flex items-center gap-3 text-slate-500">
              <Inbox size={18} className="text-sky-400" />
              <span className="text-slate-400 uppercase tracking-widest text-xs">Account:</span>
              <span className={`px-2 py-1 rounded-lg text-xs font-black border flex items-center gap-1.5 ${acctColor ? acctColor.pill : 'bg-slate-50 border-slate-200'}`}>
                {acctColor && <span className={`w-2 h-2 rounded-full ${acctColor.dot}`}></span>}
                {email.account_email}
              </span>
            </div>
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

        {/* Email body */}
        {email.body_text && (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Mail size={18} className="text-slate-400" />
              <p className="text-sm font-black text-slate-400 uppercase tracking-[0.2em]">Customer Inquiry</p>
            </div>
            <div className="text-base font-semibold text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50/50 border border-slate-100 rounded-2xl p-6 max-h-[500px] overflow-y-auto">
              {email.body_text}
            </div>
          </div>
        )}

        {/* AI Draft - Editable vs ReadOnly */}
        {email.ai_draft && (
          isHumanDraft ? (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
              className="rounded-[2rem] border-2 p-6 bg-gradient-to-br from-rose-50 to-rose-100/30 border-rose-200 shadow-lg shadow-rose-50">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <Zap size={18} className="text-rose-600" />
                  <p className="text-sm font-black text-rose-600 uppercase tracking-[0.2em]">Draft Reply — Edit before sending</p>
                </div>
                <span className="text-xs bg-rose-200 text-rose-700 px-3 py-1 rounded-full font-black uppercase tracking-wider">Not Sent Yet</span>
              </div>
              <textarea
                value={editDraftBody}
                onChange={e => setEditDraftBody(e.target.value)}
                className="w-full text-base font-bold text-slate-700 leading-relaxed border border-rose-200 rounded-2xl p-4 resize-none focus:outline-none focus:border-rose-400 focus:ring-4 focus:ring-rose-100 transition-all bg-white/70"
                rows={8}
              />
            </motion.div>
          ) : (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
              className={`rounded-[2rem] border-2 p-6 bg-gradient-to-br from-emerald-50 to-emerald-100/30 border-emerald-200 shadow-lg shadow-emerald-50`}>
              <div className="flex items-center gap-3 mb-5">
                <Zap size={18} className="text-emerald-600" />
                <p className="text-sm font-black text-emerald-600 uppercase tracking-[0.2em]">Proposed AI Response</p>
              </div>
              <p className="text-base font-bold text-slate-700 leading-relaxed whitespace-pre-wrap">{email.ai_draft}</p>
            </motion.div>
          )
        )}

        {/* Knowledge Gaps */}
        {email.followup_gaps?.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <ShieldAlert size={14} className="text-amber-500" />
              <p className="text-[10px] font-black text-amber-600 uppercase tracking-[0.2em]">
                Knowledge Deficit ({email.followup_gaps.filter(g => typeof g === 'object' ? !g.resolved : true).length} Unresolved)
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3">
              {email.followup_gaps.map((gap, i) => {
                const gapObj = typeof gap === 'string' ? { question: gap, topic: 'general' } : gap
                const resolved = gapObj.resolved
                const isOpen = activeGapIndex === i

                return (
                  <motion.div key={i} className={`rounded-2xl border-2 transition-all overflow-hidden
                    ${resolved ? 'bg-emerald-50/50 border-emerald-100' : isOpen ? 'bg-white border-indigo-300 shadow-md' : 'bg-amber-50 border-amber-100'}`}>

                    <div className="flex items-start gap-3 p-5">
                      {resolved ? <CheckCircle size={16} className="text-emerald-500 mt-0.5 flex-shrink-0" /> : <AlertCircle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />}
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-bold leading-snug ${resolved ? 'text-emerald-700' : 'text-amber-800'}`}>
                          {gapObj.question}
                        </p>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          {gapObj.topic && gapObj.topic !== 'general' && (
                            <span className="text-[10px] px-2 py-1 rounded-lg bg-slate-100 text-slate-500 font-black uppercase tracking-wider">{gapObj.topic}</span>
                          )}
                          {gapObj.product_name && (
                            <span className="text-[10px] px-2 py-1 rounded-lg bg-indigo-50 text-indigo-600 font-black uppercase tracking-wider">{gapObj.product_name}</span>
                          )}
                          {resolved && gapObj.answer && (
                            <span className="text-xs font-bold text-emerald-600 italic truncate max-w-sm">"{gapObj.answer}"</span>
                          )}
                        </div>
                      </div>

                      {!resolved && email.status === 'draft_ready' && (
                        <button onClick={() => setActiveGapIndex(isOpen ? null : i)}
                          className={`flex-shrink-0 text-xs font-black px-4 py-2 rounded-xl transition-all uppercase tracking-wider
                            ${isOpen ? 'bg-slate-100 text-slate-600 hover:bg-slate-200' : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md shadow-indigo-200'}`}>
                          {isOpen ? 'Cancel' : 'Fill Gap'}
                        </button>
                      )}
                    </div>

                    {/* Inline resolve form */}
                    <AnimatePresence>
                      {isOpen && !resolved && (
                        <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="border-t border-indigo-100 bg-indigo-50/30">
                          <div className="p-5">
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
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                )
              })}
            </div>
          </div>
        )}

        {/* Resolution note */}
        {(email.label === 'Grievance' || email.label === 'Support') && email.status === 'pending_human' && !email.resolved_at && (
          <div className="space-y-3">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Resolution Strategy</p>
            <textarea value={note} onChange={e => setNote(e.target.value)}
              placeholder="Detail the resolution steps taken..."
              className="w-full text-sm font-bold text-slate-700 border border-slate-200 rounded-2xl p-4 resize-none h-28 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 transition-all placeholder:text-slate-300" />
          </div>
        )}
      </div>

      {/* Action bar */}
      <div className="px-8 py-5 border-t border-gray-100 bg-gray-50/50">
        <div className="flex gap-3 flex-wrap">
          {/* Grievance / Support editable draft ready */}
          {isHumanDraft && (
            <>
              <button onClick={handleApprove} disabled={acting === 'approve'}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl bg-rose-600 text-white text-sm font-bold hover:bg-rose-700 transition-all disabled:opacity-60 shadow-lg shadow-rose-200">
                <Send size={16} />
                {acting === 'approve' ? 'Sending...' : 'Send Reply'}
              </button>
              <button onClick={handleResolve} disabled={acting === 'resolve'}
                className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-white border border-slate-200 text-slate-600 text-sm font-bold hover:bg-slate-50 transition-all disabled:opacity-60 shadow-sm">
                <CheckCircle size={16} />
                {acting === 'resolve' ? 'Resolving...' : 'Resolve Without Reply'}
              </button>
            </>
          )}

          {/* Sales / Read-only draft ready */}
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

          {/* Pending human fallback */}
          {(email.label === 'Support' || email.label === 'Grievance') && email.status === 'pending_human' && !email.resolved_at && (
            <button onClick={handleResolve} disabled={acting === 'resolve'}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-all disabled:opacity-60 shadow-lg shadow-indigo-200">
              <CheckCircle size={16} />
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
        </div>
      </div>
    </div>
  )
}

// ─── Compose Modal ────────────────────────────────────────────────────────────
function ComposeModal({ onClose, onSent }) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [context, setContext] = useState('')
  const [body, setBody] = useState('')
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
        setContextOpen(false)
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
      <motion.div initial={{ opacity: 0, y: 40, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 40 }} transition={{ type: 'spring', damping: 28 }}
        className="relative bg-white rounded-3xl shadow-2xl w-full max-w-3xl z-10 overflow-hidden flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-gray-100 bg-gray-50 flex-shrink-0">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-indigo-50 shadow-inner">
              <Send size={20} className="text-indigo-600" />
            </div>
            <div>
              <h2 className="text-xl font-black text-gray-900">New Direct Message</h2>
              <p className="text-sm font-bold text-gray-400">
                {aiGenerated ? 'AI draft loaded — edit directly below' : 'Add context and generate an AI draft'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-gray-200 text-gray-400 transition-all">
            <X size={20} />
          </button>
        </div>

        <div className="p-8 space-y-6 overflow-y-auto flex-1">
          {/* To + Subject */}
          <div className="space-y-4">
            <div className="flex items-center gap-4 border-b border-gray-100 pb-3">
              <span className="text-sm font-black text-gray-400 w-20 flex-shrink-0 uppercase tracking-widest">To</span>
              <input value={to} onChange={e => setTo(e.target.value)} type="email" placeholder="customer@example.com"
                className="flex-1 text-base font-bold text-gray-800 focus:outline-none placeholder:text-gray-300" />
            </div>
            <div className="flex items-center gap-4 border-b border-gray-100 pb-3">
              <span className="text-sm font-black text-gray-400 w-20 flex-shrink-0 uppercase tracking-widest">Subject</span>
              <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Re: Product Inquiry"
                className="flex-1 text-base font-bold text-gray-800 focus:outline-none placeholder:text-gray-300" />
            </div>
          </div>

          {/* Context for AI */}
          <div className="rounded-2xl border border-gray-200 overflow-hidden bg-white shadow-sm">
            <button onClick={() => setContextOpen(o => !o)} className="w-full flex items-center justify-between px-6 py-4 bg-gray-50 hover:bg-gray-100 transition-all">
              <span className="text-xs font-black text-slate-500 uppercase tracking-widest">
                Context for AI {aiGenerated && '(Used for generation)'}
              </span>
              <span className="text-xs text-gray-400">{contextOpen ? '▲' : '▼'}</span>
            </button>
            <AnimatePresence>
              {contextOpen && (
                <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
                  <textarea value={context} onChange={e => setContext(e.target.value)} rows={3}
                    placeholder="Paste the customer's question or describe what the email is about…"
                    className="w-full text-base font-bold text-gray-700 px-6 py-4 resize-none focus:outline-none border-t border-gray-100" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Main email body */}
          <div className="relative">
            {aiGenerated && (
              <div className="absolute top-4 right-4 flex items-center gap-2 z-10">
                <span className="text-xs font-black text-emerald-600 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full uppercase tracking-widest">
                  AI Draft
                </span>
                <button onClick={handleRegenerate} disabled={generating}
                  className="text-xs font-black text-indigo-600 bg-indigo-50 border border-indigo-200 px-3 py-1 rounded-full hover:bg-indigo-100 transition-all disabled:opacity-50 uppercase tracking-widest">
                  {generating ? 'Generating…' : 'Regenerate'}
                </button>
              </div>
            )}
            <textarea
              value={body}
              onChange={e => { setBody(e.target.value); setAiGenerated(false) }}
              rows={aiGenerated ? 12 : 8}
              placeholder={aiGenerated ? '' : 'Write your email here, or use "Generate AI Draft" above to auto-fill…'}
              className={`w-full text-base font-bold text-gray-800 border-2 rounded-3xl p-6 resize-none focus:outline-none transition-all shadow-inner ${aiGenerated ? 'border-emerald-200 bg-emerald-50/20 focus:border-emerald-400 focus:bg-white' : 'border-gray-200 focus:border-indigo-400'
                }`}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-8 py-6 border-t border-gray-100 bg-gray-50/60 flex-shrink-0">
          <button onClick={onClose} className="text-base font-bold text-gray-500 hover:text-gray-700 transition-colors">
            Discard
          </button>
          <div className="flex items-center gap-3">
            {!aiGenerated && (
              <button onClick={handleGenerate} disabled={!to || !subject || generating}
                className="flex items-center gap-3 px-6 py-3 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-700 text-base font-black hover:bg-indigo-100 transition-all disabled:opacity-50">
                <Zap size={16} className={generating ? 'animate-pulse' : ''} />
                {generating ? 'Generating…' : 'Generate AI Draft'}
              </button>
            )}
            <button onClick={handleSend} disabled={!to || !subject || !body || sending}
              className="flex items-center gap-3 px-8 py-3 rounded-2xl bg-emerald-600 text-white text-base font-black hover:bg-emerald-700 shadow-lg shadow-emerald-200 transition-all disabled:opacity-50">
              <Send size={16} />
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
  const [analytics, setAnalytics] = useState(null)
  const [directEmail, setDirectEmail] = useState(null)
  const [composeOpen, setComposeOpen] = useState(false)
  const [accounts, setAccounts] = useState([])
  const [activeAccount, setActiveAccount] = useState('')
  const [accountColorMap, setAccountColorMap] = useState({})
  const [acctDropdownOpen, setAcctDropdownOpen] = useState(false)

  useQueryClient()

  const fetchEmails = useCallback(() => {
    setLoading(true)
    const params = { page, limit: PAGE_SIZE }
    if (activeTab === 'needs_human') params.needs_human = true
    else if (activeTab === 'draft_ready') params.status = 'draft_ready'
    else if (activeTab === 'other') params.business_only = false
    else if (activeTab) params.label = activeTab

    if (activeTab !== 'other') params.business_only = true
    if (activeAccount) params.account_id = activeAccount

    GetGmailMessagesService(params,
      (data) => { setEmails(data?.items || []); setTotal(data?.total || 0); setLoading(false) },
      () => setLoading(false)
    )
  }, [page, activeTab, activeAccount])

  useEffect(() => { fetchEmails() }, [fetchEmails])

  const fetchAnalytics = useCallback(() => {
    GetGmailAnalyticsService("7d", activeAccount || null, res => setAnalytics(res), () => { })
  }, [activeAccount])
  useEffect(() => { fetchAnalytics() }, [fetchAnalytics])

  const syncMutation = useMutation({
    mutationFn: () => new Promise((resolve, reject) => {
      SyncGmailService(resolve, (_s, err) => reject(new Error(err)))
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

  // Load accounts & build color map
  useEffect(() => {
    GetEmailAccountsService(
      (data) => {
        const items = data?.items || []
        setAccounts(items)
        const colorMap = {}
        items.forEach((a, i) => { colorMap[a.email_address] = ACCOUNT_COLORS[i % ACCOUNT_COLORS.length] })
        setAccountColorMap(colorMap)
      }, () => { }
    )
  }, [])

  useEffect(() => { setPage(1); setSelected(null) }, [activeTab, search, activeAccount])

  const handleSync = () => syncMutation.mutate()

  useQuery({
    queryKey: ['backgroundSync'],
    queryFn: () => new Promise((resolve, reject) => {
      SyncGmailService(() => { fetchEmails(); fetchAnalytics(); resolve(true) }, (_s, err) => reject(new Error(err)))
    }),
    refetchInterval: 60000,
    refetchOnWindowFocus: true,
  })

  const syncing = syncMutation.isPending
  const filtered = search
    ? emails.filter(e => (e.subject || '').toLowerCase().includes(search.toLowerCase()) || (e.sender || '').toLowerCase().includes(search.toLowerCase()))
    : emails

  const selectedEmail = selected ? (directEmail?.id === selected ? directEmail : emails.find(e => e.id === selected)) : null
  const totalVolume = total || 0

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-[#fcf8ff] text-slate-900 px-6 py-4 md:px-10 md:py-6 relative overflow-hidden font-sans">

      <div className="max-w-[1500px] mx-auto space-y-6 relative z-10">

        {/* Header Section */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-200">
                <Mail size={18} />
              </div>
              <span className="text-sm font-black text-indigo-600 uppercase tracking-[0.2em]">Communications</span>
            </div>
            <h1 className="text-4xl font-black tracking-tight text-slate-900">
              Intelligence <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-500">Inbox</span>
            </h1>
            <p className="text-slate-500 font-bold text-base">Managing AI-driven interactions across all connected identities.</p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Accounts Filter UI */}
            {accounts.length > 1 && (
              <div className="relative">
                <button onClick={() => setAcctDropdownOpen(!acctDropdownOpen)}
                  className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-slate-100 shadow-sm text-sm font-black text-slate-700 hover:bg-slate-50 transition-all">
                  <Inbox size={16} className="text-indigo-400" />
                  {activeAccount ? accounts.find(a => a.id === activeAccount)?.email_address : 'All Accounts'}
                  <ChevronDown size={14} className={`ml-2 transition-transform ${acctDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

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
            )}

            <div className="flex items-center gap-3 pl-2">
              <div className="flex items-center gap-3 px-5 py-3 rounded-2xl bg-white border border-slate-100 shadow-sm">
                <Users size={18} className="text-indigo-400" />
                <div className="flex flex-col">
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Total Vol.</span>
                  <span className="text-lg font-black text-slate-900 leading-none">{totalVolume}</span>
                </div>
              </div>
              <button onClick={handleSync} disabled={syncing}
                className="flex items-center gap-3 px-6 py-3 rounded-2xl bg-indigo-600 text-white text-base font-black shadow-lg shadow-indigo-200 hover:bg-indigo-700 transition-all disabled:opacity-60">
                <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
                {syncing ? 'Syncing...' : 'Force Sync'}
              </button>
              <button onClick={() => setComposeOpen(true)}
                className="flex items-center gap-3 px-6 py-3 rounded-2xl bg-white border border-slate-200 text-slate-800 text-base font-black shadow-sm hover:shadow-xl hover:border-indigo-100 transition-all">
                <Send size={16} className="text-emerald-500" />
                Direct Message
              </button>
            </div>
          </div>
        </div>

        {/* Main Two-Panel Interface */}
        <div className="flex gap-0 premium-glass rounded-[2rem] overflow-hidden shadow-2xl border-white/40" style={{ height: '75vh' }}>

          {/* Left Panel: Inbox List */}
          <div className="w-96 flex-shrink-0 flex flex-col border-r border-slate-100 bg-white/40 backdrop-blur-md">
            {/* Tabs */}
            <div className="overflow-x-auto border-b border-slate-100 px-4">
              <div className="flex gap-4">
                {TABS.map(tab => {
                  const Icon = tab.icon
                  let count = 0
                  if (tab.key === "") count = analytics?.total_emails || 0
                  else if (tab.key === "needs_human") count = analytics?.pending_human || 0
                  else if (tab.key === "draft_ready") count = analytics?.draft_ready || 0
                  else count = analytics?.by_label?.[tab.key] || 0

                  return (
                    <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-2 px-3 py-4 text-sm font-black uppercase tracking-[0.1em] border-b-2 transition-all whitespace-nowrap
                      ${activeTab === tab.key ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-400 hover:text-slate-600'}`}>
                      <Icon size={16} />
                      {tab.label}
                      {count > 0 && (
                        <span className={`ml-1 px-1.5 py-0.5 rounded-md text-[10px] leading-none ${activeTab === tab.key ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-100 text-slate-500'}`}>
                          {count}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Search */}
            <div className="px-4 py-4 border-b border-gray-100">
              <div className="relative">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search signals..."
                  className="w-full pl-10 pr-4 py-3 text-base font-bold rounded-xl bg-gray-50 border border-gray-200 text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-indigo-400 transition-all" />
              </div>
            </div>

            {/* Email List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <RefreshCw size={32} className="text-indigo-400 animate-spin" />
                  <p className="text-base font-black text-slate-400 uppercase tracking-widest">Scanning Network...</p>
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
                  {filtered.map(email => (
                    <motion.div key={email.id} variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}>
                      <EmailRow email={email} selected={selected === email.id} onClick={() => setSelected(selected === email.id ? null : email.id)} accountColorMap={accountColorMap} />
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between px-8 py-5 border-t border-slate-100 bg-white/60 backdrop-blur-sm">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 transition-colors">
                  <ChevronRight size={18} className="rotate-180" /> Prev
                </button>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-black text-slate-900">{page}</span>
                  <span className="text-sm font-bold text-slate-300">/</span>
                  <span className="text-sm font-black text-slate-400">{Math.ceil(total / PAGE_SIZE)}</span>
                </div>
                <button disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)} className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 transition-colors">
                  Next <ChevronRight size={18} />
                </button>
              </div>
            )}
          </div>

          {/* Right Panel: Detail View */}
          <div className="flex-1 min-w-0 bg-white/90 backdrop-blur-xl">
            <AnimatePresence mode="wait">
              {selectedEmail ? (
                <motion.div key={selectedEmail.id} className="h-full" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                  <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); setSelected(null) }} accountColorMap={accountColorMap} />
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
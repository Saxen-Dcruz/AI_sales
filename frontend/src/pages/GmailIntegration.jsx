import { Float, MeshDistortMaterial, Sphere } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Archive,
  CheckCircle,
  ChevronRight,
  Clock,
  Cpu,
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
import { ApproveDraftService, DiscardDraftService, GenerateDraftService, GetEmailByIdService, GetGmailAnalyticsService, GetGmailMessagesService, ResolveEmailService, SendEmailService, SyncGmailService } from '../services/ApiService'

// ─── Config ──────────────────────────────────────────────────────────────────

// ─── Config & Colors ────────────────────────────────────────────────────────

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
  { key: '', label: 'All', icon: MessageSquare },
  { key: 'Sales', label: 'Sales', icon: Zap },
  { key: 'Support', label: 'Support', icon: Users },
  { key: 'Grievance', label: 'Grievance', icon: AlertCircle },
  { key: 'Transactional', label: 'Transactional', icon: Send },
  { key: 'Promotional', label: 'Promotional', icon: Tag },
  { key: 'needs_human', label: 'Needs Review', icon: Star },
  { key: 'draft_ready', label: 'Drafts', icon: CheckCircle },
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
              <MeshDistortMaterial
                color={COLORS.indigo}
                speed={3}
                distort={0.4}
                roughness={0.2}
                metalness={0.8}
                transparent
                opacity={0.6}
              />
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

function EmailRow({ email, selected, onClick }) {
  const labelCfg = LABEL_CONFIG[email.label] || LABEL_CONFIG.Unclassified
  const statusCfg = STATUS_CONFIG[email.status] || STATUS_CONFIG.classified
  const StatusIcon = statusCfg.icon
  const isUnread = email.status === 'new'

  return (
    <button onClick={onClick}
      className={`w-full text-left border-l-[3px] px-5 py-4 transition-all
        ${selected ? 'bg-indigo-50/50 border-l-indigo-600' : `hover:bg-slate-50/50 ${labelCfg.border}`}
        ${email.needs_human ? 'bg-rose-50/20' : ''}
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
          {isUnread && (
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-indigo-600 rounded-full border-2 border-white" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Top row: sender + time */}
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className={`text-lg truncate tracking-tight ${isUnread ? 'font-extrabold text-slate-900' : 'font-bold text-slate-700'}`}>
              {senderName(email.sender)}
            </span>
            <span className="text-sm font-bold text-slate-400 flex-shrink-0 uppercase tracking-tighter">{relTime(email.received_at)}</span>
          </div>
          {/* Subject */}
          <p className={`text-base truncate leading-tight ${isUnread ? 'font-bold text-slate-800' : 'font-semibold text-slate-500'}`}>
            {email.subject || '(no subject)'}
          </p>
          {/* Bottom row: badges */}
          <div className="flex items-center gap-2 mt-2">
            <span className={`text-xs font-black px-2.5 py-1 rounded-lg uppercase tracking-wider ${labelCfg.badge}`}>
              {email.label || 'Unclassified'}
            </span>
            {email.needs_human && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-rose-100 text-rose-600 uppercase tracking-wider">
                Review
              </span>
            )}
            {email.status === 'draft_ready' && (
              <span className="text-xs font-black px-2.5 py-1 rounded-lg bg-amber-100 text-amber-600 uppercase tracking-wider">
                Draft
              </span>
            )}
            <div className="ml-auto opacity-40 group-hover:opacity-100 transition-opacity">
              <StatusIcon size={12} className={`${statusCfg.color}`} />
            </div>
          </div>
        </div>

        <ChevronRight size={14} className={`flex-shrink-0 transition-transform ${selected ? 'text-indigo-600 translate-x-1' : 'text-slate-300'}`} />
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
        {/* From / Date */}
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
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-8">

        {/* Classifier reasoning */}
        {email.classifier_reasoning && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100/50"
          >
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

        {/* AI Draft */}
        {email.ai_draft && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`rounded-[2rem] border-2 p-6 bg-gradient-to-br from-emerald-50 to-emerald-100/30 border-emerald-200 shadow-lg shadow-emerald-50`}
          >
            <div className="flex items-center gap-3 mb-5">
              <Zap size={18} className="text-emerald-600" />
              <p className="text-sm font-black text-emerald-600 uppercase tracking-[0.2em]">Proposed AI Response</p>
            </div>
            <p className="text-base font-bold text-slate-700 leading-relaxed whitespace-pre-wrap">{email.ai_draft}</p>
          </motion.div>
        )}

        {/* Gaps */}
        {email.followup_gaps?.length > 0 && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <ShieldAlert size={14} className="text-amber-500" />
              <p className="text-[10px] font-black text-amber-600 uppercase tracking-[0.2em]">
                Knowledge Deficit ({email.followup_gaps.filter(g => !g.resolved).length} Unresolved)
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {email.followup_gaps.map((gap, i) => {
                const q = typeof gap === 'string' ? gap : gap.question
                const resolved = typeof gap === 'object' && gap.resolved
                return (
                  <motion.div
                    key={i}
                    whileHover={{ x: 4 }}
                    className={`flex items-start gap-3 p-4 rounded-2xl text-xs font-bold transition-all
                    ${resolved ? 'bg-emerald-50/50 text-emerald-700 border border-emerald-100' : 'bg-amber-50 text-amber-700 border border-amber-100'}`}
                  >
                    {resolved ? <CheckCircle size={14} className="mt-0.5 flex-shrink-0" /> :
                      <AlertCircle size={14} className="mt-0.5 flex-shrink-0" />}
                    <span>{q}</span>
                  </motion.div>
                )
              })}
            </div>
          </div>
        )}

        {/* Resolution note (for Grievance/Support) */}
        {(email.label === 'Grievance' || email.label === 'Support') && email.status !== 'replied' && !email.resolved_at && (
          <div className="space-y-3">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Resolution Strategy</p>
            <textarea value={note} onChange={e => setNote(e.target.value)}
              placeholder="Detail the resolution steps taken..."
              className="w-full text-xs font-bold text-slate-700 border border-slate-200 rounded-2xl p-4 resize-none h-28 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-50 transition-all placeholder:text-slate-300" />
          </div>
        )}

      </div>

      {/* Action bar */}
  <div className="px-6 py-5 border-t border-gray-100 bg-gray-50/50">
    <div className="flex gap-3 flex-wrap">
      {email.status === 'draft_ready' && email.ai_draft && (
        <>
          <button onClick={handleApprove} disabled={acting === 'approve'}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 transition-all disabled:opacity-60">
            <Send size={14} />
            {acting === 'approve' ? 'Sending...' : 'Approve & Send'}
          </button>
          <button onClick={handleDiscard} disabled={acting === 'discard'}
            className="flex items-center gap-2 px-4 py-3 rounded-xl bg-gray-100 text-gray-600 text-sm font-medium hover:bg-gray-200 transition-all disabled:opacity-60">
            <X size={14} />
            Discard
          </button>
        </>
      )}
      {(email.label === 'Support' || email.label === 'Grievance') &&
        email.status !== 'replied' && !email.resolved_at && (
          <button onClick={handleResolve} disabled={acting === 'resolve'}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all disabled:opacity-60">
            <CheckCircle size={14} />
            {acting === 'resolve' ? 'Resolving...' : 'Mark Resolved'}
          </button>
        )}
      {email.status === 'replied' && (
        <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium">
          <CheckCircle size={16} />
          Replied
        </div>
      )}
      {email.resolved_at && (
        <div className="flex items-center gap-2 text-sm text-gray-500 font-bold">
          <CheckCircle size={16} className="text-emerald-500" />
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
              <h2 className="text-lg font-black text-gray-900">New Email</h2>
              <p className="text-xs font-bold text-gray-400">
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
            <div className="flex items-center gap-4">
              <span className="text-sm font-black text-gray-400 w-20 flex-shrink-0 uppercase tracking-widest">To</span>
              <input value={to} onChange={e => setTo(e.target.value)} type="email"
                placeholder="customer@example.com"
                className="flex-1 text-base font-bold text-gray-800 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-400 transition-all" />
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm font-black text-gray-400 w-20 flex-shrink-0 uppercase tracking-widest">Subject</span>
              <input value={subject} onChange={e => setSubject(e.target.value)}
                placeholder="Re: Product Inquiry"
                className="flex-1 text-base font-bold text-gray-800 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-400 transition-all" />
            </div>
          </div>

          {/* Context body (always visible) */}
          <div>
            <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">
              Customer's message / context for AI
            </p>
            <textarea value={body} onChange={e => setBody(e.target.value)} rows={4}
              placeholder="Paste the customer's question or describe what the email is about..."
              className="w-full text-base font-bold text-gray-700 border border-gray-200 rounded-xl px-4 py-3 resize-none focus:outline-none focus:border-indigo-400 transition-all" />
          </div>

          {/* AI Draft section */}
          <AnimatePresence>
            {step === 'draft' && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 overflow-hidden">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-emerald-200">
                    <p className="text-xs font-black text-emerald-700 uppercase tracking-widest">
                      AI Draft — edit before sending
                    </p>
                    <button onClick={() => setStep('compose')}
                      className="text-xs font-bold text-emerald-600 hover:text-emerald-800 underline">
                      Regenerate
                    </button>
                  </div>
                  <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={10}
                    className="w-full text-base font-bold text-gray-800 bg-transparent px-5 py-4 resize-none focus:outline-none" />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-6 py-5 border-t border-gray-100 bg-gray-50/60">
          <button onClick={onClose} className="text-base font-bold text-gray-500 hover:text-gray-700 transition-colors">
            Discard
          </button>
          <div className="flex items-center gap-3">
            {step === 'compose' ? (
              <button onClick={handleGenerate} disabled={!to || !subject || generating}
                className="flex items-center gap-3 px-6 py-3 rounded-2xl bg-indigo-600 text-white text-base font-black hover:bg-indigo-700 shadow-lg shadow-indigo-100 transition-all disabled:opacity-50">
                <Zap size={16} className={generating ? 'animate-pulse' : ''} />
                {generating ? 'Generating...' : 'Generate AI Draft'}
              </button>
            ) : (
              <>
                <button onClick={() => setStep('compose')}
                  className="px-6 py-3 rounded-2xl bg-gray-100 text-gray-600 text-base font-black hover:bg-gray-200 transition-all">
                  Edit Details
                </button>
                <button onClick={handleSend} disabled={!draft || sending}
                  className="flex items-center gap-3 px-6 py-3 rounded-2xl bg-emerald-600 text-white text-base font-black hover:bg-emerald-700 shadow-lg shadow-emerald-100 transition-all disabled:opacity-50">
                  <Send size={16} />
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
  // const [syncing, setSyncing] = useState(false)
  const [activeTab, setActiveTab] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [directEmail, setDirectEmail] = useState(null) // email fetched directly from gaps nav
  const [composeOpen, setComposeOpen] = useState(false)

  const fetchAnalytics = useCallback(() => {
    GetGmailAnalyticsService(
      (res) => setAnalytics(res),
      () => {}
    )
  }, [])

  useEffect(() => {
    fetchAnalytics()
  }, [fetchAnalytics])

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

  const syncMutation = useMutation({
    mutationFn: () => new Promise((resolve, reject) => {
      SyncGmailService(
        resolve,
        (s, err) => reject(new Error(err))
      )
    }),
    onSuccess: () => {
      fetchEmails()
      fetchAnalytics()
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
  
  // Reset page and selection when tab or search changes
  useEffect(() => { 
    setPage(1); 
    setSelected(null); 
  }, [activeTab, search])

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
        (s, err) => reject(new Error(err))
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
      (e.sender || '').toLowerCase().includes(search.toLowerCase()) ||   
      (e.body_text || '').toLowerCase().includes(search.toLowerCase()) ||
      (e.label || '').toLowerCase().includes(search.toLowerCase())
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
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-[#fcf8ff] text-slate-900 px-6 py-4 md:px-10 md:py-6 relative overflow-hidden font-sans">

      {/* Background 3D Aura */}
      {/*  */}

      <div className="max-w-[1500px] mx-auto space-y-4 relative z-10">

        {/* Header + Stats Section */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
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
            <p className="text-slate-500 font-bold text-base">Managing AI-driven customer interactions and sentiment analysis</p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-white border border-slate-100 shadow-sm">
              <Users size={16} className="text-indigo-400" />
              <div className="flex flex-col">
                <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Total Volume</span>
                <span className="text-lg font-black text-slate-900 leading-none">{total}</span>
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

        {/* Main two-panel layout */}
        <div className="flex gap-0 premium-glass rounded-[2rem] overflow-hidden shadow-2xl border-white/40" style={{ height: '75vh' }}>

          {/* Left: list */}
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
                    <button key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-2 px-3 py-4 text-sm font-black uppercase tracking-[0.1em] border-b-2 transition-all whitespace-nowrap
                      ${activeTab === tab.key
                          ? 'border-indigo-600 text-indigo-600'
                          : 'border-transparent text-slate-400 hover:text-slate-600'}`}>
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
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search emails..."
                  className="w-full pl-10 pr-4 py-3 text-base font-bold rounded-xl bg-gray-50 border border-gray-200 text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-indigo-400 transition-all" />
              </div>
            </div>

            {/* Email list */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <RefreshCw size={32} className="text-indigo-400 animate-spin" />
                  <p className="text-base font-black text-slate-400 uppercase tracking-widest">Scanning Intelligence Feed...</p>
                </div>
              ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4 text-center px-6">
                  <div className="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-200 shadow-inner">
                    <MailOpen size={32} />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-900 uppercase tracking-wider">No signals detected</p>
                    <p className="text-base font-bold text-slate-400 mt-2">Try adjusting your filters or search query</p>
                  </div>
                </div>
              ) : (
                <motion.div 
                  initial="hidden"
                  animate="visible"
                  variants={{
                    visible: { transition: { staggerChildren: 0.05 } }
                  }}
                  className="divide-y divide-slate-100"
                >
                  {filtered.map(email => (
                    <motion.div key={email.id}
                      variants={{
                        hidden: { opacity: 0, x: -10 },
                        visible: { opacity: 1, x: 0 }
                      }}
                    >
                      <EmailRow
                        email={email}
                        selected={selected === email.id}
                        onClick={() => setSelected(selected === email.id ? null : email.id)}
                      />
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
              <div className="flex items-center justify-between px-8 py-5 border-t border-slate-100 bg-white/60 backdrop-blur-sm">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                  className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                  <ChevronRight size={18} className="rotate-180" /> Prev
                </button>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-black text-slate-900">{page}</span>
                  <span className="text-sm font-bold text-slate-300">/</span>
                  <span className="text-sm font-black text-slate-400">{Math.ceil(total / PAGE_SIZE)}</span>
                </div>
                <button disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)}
                  className="flex items-center gap-2 text-sm font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                  Next <ChevronRight size={18} />
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
                  <p className="text-base font-bold text-gray-400">Select an email to read</p>
                  <div className="mt-4 grid grid-cols-2 gap-3 w-full max-w-sm">
                    {Object.entries(LABEL_CONFIG).filter(([k]) => k !== 'Unclassified').map(([label, cfg]) => {
                      const count = emails.filter(e => e.label === label).length
                      if (!count) return null
                      return (
                        <button key={label} onClick={() => setActiveTab(label)}
                          className={`flex items-center justify-between px-4 py-3 rounded-2xl border ${cfg.badge} border-transparent hover:shadow-lg hover:scale-105 transition-all`}>
                          <span className="text-xs font-black uppercase tracking-wider">{label}</span>
                          <span className="text-xs font-black">{count}</span>
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
      </div>

    </motion.div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle, Archive, CheckCircle, ChevronRight,
  MessageCircle, MessageSquare, Phone, RefreshCw,
  Search, Send, Tag, Users, X, Zap, Plus, Trash2,
  ToggleLeft, ToggleRight, Settings
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  GetWhatsAppMessagesService, GetWhatsAppMessageService,
  ApproveWhatsAppDraftService, DiscardWhatsAppDraftService,
  ResolveWhatsAppMessageService, ResolveWhatsAppGapService,
  GetWhatsAppGapsService, SendWhatsAppMessageService,
  GetWhatsAppAnalyticsService, GetWhatsAppAccountsService,
  AddWhatsAppAccountService, UpdateWhatsAppAccountService,
  DeleteWhatsAppAccountService, SetPrimaryWhatsAppAccountService,
} from '../services/ApiService'

// ── Config ─────────────────────────────────────────────────────────────────────

const LABEL_CONFIG = {
  Sales:         { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700' },
  Support:       { bg: 'bg-blue-50',    text: 'text-blue-700',    dot: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700'    },
  Grievance:     { bg: 'bg-red-50',     text: 'text-red-700',     dot: 'bg-red-500',     badge: 'bg-red-100 text-red-700'     },
  Transactional: { bg: 'bg-gray-50',    text: 'text-gray-600',    dot: 'bg-gray-400',    badge: 'bg-gray-100 text-gray-600'    },
  Promotional:   { bg: 'bg-purple-50',  text: 'text-purple-700',  dot: 'bg-purple-400',  badge: 'bg-purple-100 text-purple-700' },
  Personal:      { bg: 'bg-pink-50',    text: 'text-pink-700',    dot: 'bg-pink-400',    badge: 'bg-pink-100 text-pink-700'    },
  Unclassified:  { bg: 'bg-gray-50',    text: 'text-gray-500',    dot: 'bg-gray-300',    badge: 'bg-gray-100 text-gray-500'    },
}

const STATUS_CONFIG = {
  new:           { icon: MessageSquare, color: 'text-blue-500',    label: 'New' },
  classified:    { icon: Tag,           color: 'text-gray-400',    label: 'Classified' },
  draft_ready:   { icon: Zap,           color: 'text-amber-500',   label: 'Draft Ready' },
  pending_human: { icon: AlertCircle,   color: 'text-red-500',     label: 'Needs Review' },
  replied:       { icon: CheckCircle,   color: 'text-emerald-500', label: 'Replied' },
  archived:      { icon: Archive,       color: 'text-gray-400',    label: 'Archived' },
  ignored:       { icon: X,            color: 'text-gray-300',    label: 'Ignored' },
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' })
}

function initials(phone) {
  if (!phone) return 'WA'
  const digits = phone.replace(/\D/g, '')
  return digits.slice(-2)
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function Toast({ msg, type, onDone }) {
  useEffect(() => { const t = setTimeout(onDone, 3500); return () => clearTimeout(t) }, [onDone])
  return (
    <div className={`fixed top-20 right-5 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium
      ${type === 'error' ? 'bg-red-50 text-red-700 border border-red-200'
                         : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
      {msg}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function WhatsAppIntegration() {
  const qc = useQueryClient()

  const [activeTab, setActiveTab]     = useState('inbox')    // 'inbox' | 'analytics' | 'settings'
  const [selectedId, setSelectedId]   = useState(null)
  const [searchTerm, setSearchTerm]   = useState('')
  const [filterLabel, setFilterLabel] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [toast, setToast]             = useState(null)
  const [composeOpen, setComposeOpen] = useState(false)
  const [composeData, setComposeData] = useState({ account_id: '', to_number: '', body: '' })
  const [draftEdit, setDraftEdit]     = useState('')
  const [settingsTab, setSettingsTab] = useState('accounts')  // only 'accounts' for now

  const showToast = (msg, type = 'success') => setToast({ msg, type })

  // ── Queries ──────────────────────────────────────────────────────────────────

  const { data: messagesData, isLoading: msgsLoading } = useQuery({
    queryKey: ['wa-messages', filterLabel, filterStatus],
    queryFn: () => new Promise((res, rej) =>
      GetWhatsAppMessagesService(
        { label: filterLabel || undefined, status: filterStatus || undefined, limit: 50 },
        res, (_, e) => rej(e)
      )
    ),
    enabled: activeTab === 'inbox',
  })

  const { data: selectedMsg } = useQuery({
    queryKey: ['wa-message', selectedId],
    queryFn: () => new Promise((res, rej) =>
      GetWhatsAppMessageService(selectedId, res, (_, e) => rej(e))
    ),
    enabled: !!selectedId,
  })

  const { data: analyticsData } = useQuery({
    queryKey: ['wa-analytics'],
    queryFn: () => new Promise((res, rej) => GetWhatsAppAnalyticsService(res, (_, e) => rej(e))),
    enabled: activeTab === 'analytics',
  })

  const { data: accountsData, isLoading: accsLoading } = useQuery({
    queryKey: ['wa-accounts'],
    queryFn: () => new Promise((res, rej) => GetWhatsAppAccountsService(res, (_, e) => rej(e))),
    enabled: activeTab === 'settings' || composeOpen,
  })

  // ── Mutations ────────────────────────────────────────────────────────────────

  const approveMut = useMutation({
    mutationFn: ({ id, body }) => new Promise((res, rej) =>
      ApproveWhatsAppDraftService(id, { edit_body: body || null }, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-messages'] })
      qc.invalidateQueries({ queryKey: ['wa-message', selectedId] })
      showToast('Reply sent via WhatsApp')
    },
    onError: (e) => showToast(e || 'Send failed', 'error'),
  })

  const discardMut = useMutation({
    mutationFn: (id) => new Promise((res, rej) =>
      DiscardWhatsAppDraftService(id, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-messages'] })
      qc.invalidateQueries({ queryKey: ['wa-message', selectedId] })
      showToast('Draft discarded — flagged for human review')
    },
  })

  const resolveMut = useMutation({
    mutationFn: (id) => new Promise((res, rej) =>
      ResolveWhatsAppMessageService(id, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-messages'] })
      qc.invalidateQueries({ queryKey: ['wa-message', selectedId] })
      showToast('Message marked as resolved')
    },
  })

  const gapResolveMut = useMutation({
    mutationFn: ({ id, gap_index, answer }) => new Promise((res, rej) =>
      ResolveWhatsAppGapService(id, { gap_index, answer }, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-message', selectedId] })
      showToast('Answer saved to knowledge base')
    },
    onError: (e) => showToast(e || 'Failed to save gap answer', 'error'),
  })

  const sendMut = useMutation({
    mutationFn: (data) => new Promise((res, rej) =>
      SendWhatsAppMessageService(data, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-messages'] })
      setComposeOpen(false)
      setComposeData({ account_id: '', to_number: '', body: '' })
      showToast('Message sent')
    },
    onError: (e) => showToast(e || 'Send failed', 'error'),
  })

  const addAccountMut = useMutation({
    mutationFn: (data) => new Promise((res, rej) =>
      AddWhatsAppAccountService(data, res, (_, e) => rej(new Error(e)))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-accounts'] })
      showToast('WhatsApp account connected')
    },
    onError: (e) => showToast(e?.message || 'Failed to add account', 'error'),
  })

  const deleteAccountMut = useMutation({
    mutationFn: (id) => new Promise((res, rej) =>
      DeleteWhatsAppAccountService(id, res, (_, e) => rej(e))
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wa-accounts'] })
      showToast('Account removed')
    },
  })

  const toggleAutoSendMut = useMutation({
    mutationFn: ({ id, auto_send }) => new Promise((res, rej) =>
      UpdateWhatsAppAccountService(id, { auto_send }, res, (_, e) => rej(e))
    ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wa-accounts'] }),
  })

  // ── Filtered messages ─────────────────────────────────────────────────────────

  const messages = (messagesData?.items || []).filter(m =>
    !searchTerm || (m.from_number || '').includes(searchTerm) ||
    (m.body || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  // ── Selection helpers ─────────────────────────────────────────────────────────

  const msg = selectedMsg || null
  const lcfg = msg ? (LABEL_CONFIG[msg.label] || LABEL_CONFIG.Unclassified) : null

  useEffect(() => {
    if (msg) setDraftEdit(msg.ai_draft || '')
  }, [msg?.id])

  // ── Add account form state ────────────────────────────────────────────────────

  const [addForm, setAddForm] = useState({
    phone_number_id: '', waba_id: '', access_token: '',
    verify_token: '', display_phone: '', display_name: '', auto_send: false,
  })
  const [addFormOpen, setAddFormOpen] = useState(false)

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {toast && <Toast msg={toast.msg} type={toast.type} onDone={() => setToast(null)} />}

      {/* ── Header ── */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#25D366] flex items-center justify-center">
            <MessageCircle size={16} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900">WhatsApp Inbox</h1>
            <p className="text-xs text-gray-500">RDL Sales Intelligence — Meta Cloud API</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setComposeOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#25D366] text-white text-xs font-medium rounded-lg hover:bg-[#128C7E] transition-colors"
          >
            <Send size={13} /> New Message
          </button>
          {['inbox', 'analytics', 'settings'].map(t => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors capitalize
                ${activeTab === t ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* ── Body ── */}
      {activeTab === 'inbox' && (
        <div className="flex flex-1 overflow-hidden">

          {/* ── Left sidebar: label nav + message list ── */}
          <div className="w-80 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col">
            {/* Search */}
            <div className="p-3 border-b border-gray-100">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-2.5 text-gray-400" />
                <input
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  placeholder="Search phone or message…"
                  className="w-full pl-8 pr-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                />
              </div>
            </div>

            {/* Label filters — Gmail-style clickable labels */}
            <div className="p-2 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-400 px-1 mb-1.5">LABELS</p>
              <div className="space-y-0.5">
                {[
                  { label: '',             display: 'All Messages',  dot: 'bg-gray-500'    },
                  { label: 'Sales',        display: 'Sales',         dot: 'bg-emerald-500' },
                  { label: 'Support',      display: 'Support',       dot: 'bg-blue-500'    },
                  { label: 'Grievance',    display: 'Grievance',     dot: 'bg-red-500'     },
                  { label: 'Transactional',display: 'Transactional', dot: 'bg-orange-400'  },
                  { label: 'Promotional',  display: 'Promotional',   dot: 'bg-purple-400'  },
                  { label: 'Personal',     display: 'Personal',      dot: 'bg-pink-400'    },
                  { label: 'Unclassified', display: 'Unclassified',  dot: 'bg-gray-300'    },
                ].map(({ label, display, dot }) => {
                  const allItems = messagesData?.items || []
                  const count = label
                    ? allItems.filter(m => m.label === label).length
                    : (messagesData?.total || 0)
                  const isActive = filterLabel === label
                  return (
                    <button
                      key={display}
                      onClick={() => { setFilterLabel(label); setSelectedId(null) }}
                      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors
                        ${isActive
                          ? 'bg-[#25D366]/10 text-gray-900 font-semibold'
                          : 'text-gray-600 hover:bg-gray-50'}`}
                    >
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
                      <span className="flex-1 text-left">{display}</span>
                      <span className={`text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center
                        ${isActive
                          ? 'bg-[#25D366] text-white'
                          : count > 0 ? 'bg-gray-100 text-gray-600' : 'text-gray-300'}`}>
                        {count}
                      </span>
                    </button>
                  )
                })}
              </div>

              {/* Status quick-filter */}
              <div className="flex gap-1 mt-2 flex-wrap">
                {[
                  { v: '',             label: 'All'    },
                  { v: 'draft_ready',  label: 'Drafts' },
                  { v: 'pending_human',label: 'Review' },
                  { v: 'replied',      label: 'Replied'},
                ].map(s => (
                  <button
                    key={s.v}
                    onClick={() => setFilterStatus(s.v)}
                    className={`px-2 py-0.5 rounded-full text-xs transition-colors
                      ${filterStatus === s.v
                        ? 'bg-gray-800 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Message list */}
            <div className="flex-1 overflow-y-auto">
              {msgsLoading && (
                <div className="flex items-center justify-center h-24 text-xs text-gray-400">
                  <RefreshCw size={14} className="animate-spin mr-2" /> Loading…
                </div>
              )}
              {!msgsLoading && messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-48 text-gray-400">
                  <MessageCircle size={32} className="mb-2 opacity-30" />
                  <p className="text-xs">No messages found</p>
                </div>
              )}
              {messages.map(m => {
                const cfg = LABEL_CONFIG[m.label] || LABEL_CONFIG.Unclassified
                const scfg = STATUS_CONFIG[m.status] || STATUS_CONFIG.new
                const StatusIcon = scfg.icon
                const isSelected = m.id === selectedId
                return (
                  <div
                    key={m.id}
                    onClick={() => setSelectedId(m.id)}
                    className={`p-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors border-l-[3px]
                      ${isSelected
                        ? 'bg-emerald-50 border-l-[#25D366]'
                        : `border-l-transparent`}`}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Avatar with label color ring */}
                      <div className="relative flex-shrink-0">
                        <div className="w-8 h-8 rounded-full bg-[#25D366] flex items-center justify-center text-white text-xs font-bold">
                          {initials(m.from_number)}
                        </div>
                        {/* Label dot in corner */}
                        <span className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white ${cfg.dot}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-gray-900 truncate">{m.from_number}</span>
                          <span className="text-xs text-gray-400 flex-shrink-0 ml-1">{fmtTime(m.received_at)}</span>
                        </div>
                        <p className="text-xs text-gray-500 truncate mt-0.5">{m.body || '(no text)'}</p>
                        <div className="flex items-center gap-1.5 mt-1">
                          {/* Label badge — prominent, same as Gmail */}
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cfg.badge}`}>
                            {m.label}
                          </span>
                          <StatusIcon size={11} className={scfg.color} />
                          {m.needs_human && (
                            <AlertCircle size={11} className="text-red-500" />
                          )}
                          {(m.followup_gaps?.length > 0) && (() => {
                            const unresolved = m.followup_gaps.filter(g => !g.resolved).length
                            return unresolved > 0 ? (
                              <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">
                                {unresolved} gap{unresolved > 1 ? 's' : ''}
                              </span>
                            ) : null
                          })()}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── Message detail ── */}
          <div className="flex-1 overflow-y-auto p-6">
            {!msg && (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <MessageCircle size={48} className="mb-3 opacity-20" />
                <p className="text-sm">Select a message to view details</p>
              </div>
            )}
            {msg && (
              <div className="max-w-2xl mx-auto space-y-4">
                {/* Header */}
                <div className={`rounded-xl border p-4 ${lcfg.bg}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-full bg-[#25D366] flex items-center justify-center text-white font-bold">
                        {initials(msg.from_number)}
                      </div>
                      <div>
                        <p className="font-semibold text-gray-900 text-sm">{msg.from_number}</p>
                        <p className="text-xs text-gray-500">via {msg.account_phone || 'WhatsApp'}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{new Date(msg.received_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-1 rounded-full font-medium ${lcfg.badge}`}>{msg.label}</span>
                      {msg.needs_human && (
                        <span className="text-xs px-2 py-1 rounded-full bg-red-100 text-red-700 font-medium">
                          Needs Review
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="mt-3 p-3 bg-white rounded-lg text-sm text-gray-800 whitespace-pre-wrap border border-white/60">
                    {msg.body || '(no text content)'}
                  </div>
                </div>

                {/* AI Draft */}
                {(msg.status === 'draft_ready' || msg.ai_draft) && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Zap size={14} className="text-amber-600" />
                      <span className="text-xs font-semibold text-amber-700">AI Draft Reply</span>
                      <span className="text-xs text-amber-600 ml-auto">Edit before sending</span>
                    </div>
                    <textarea
                      value={draftEdit}
                      onChange={e => setDraftEdit(e.target.value)}
                      rows={5}
                      className="w-full text-sm p-3 bg-white border border-amber-200 rounded-lg resize-none focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    />
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => approveMut.mutate({ id: msg.id, body: draftEdit })}
                        disabled={approveMut.isPending}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-[#25D366] text-white text-xs font-medium rounded-lg hover:bg-[#128C7E] disabled:opacity-50"
                      >
                        <Send size={12} />
                        {approveMut.isPending ? 'Sending…' : 'Send via WhatsApp'}
                      </button>
                      <button
                        onClick={() => discardMut.mutate(msg.id)}
                        disabled={discardMut.isPending}
                        className="px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                      >
                        Discard Draft
                      </button>
                    </div>
                  </div>
                )}

                {/* Knowledge Gaps */}
                {(msg.followup_gaps?.length > 0) && (
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <AlertCircle size={14} className="text-red-600" />
                      <span className="text-xs font-semibold text-red-700">
                        Knowledge Gaps — Fill these to improve future AI replies
                      </span>
                    </div>
                    <div className="space-y-3">
                      {msg.followup_gaps.map((gap, i) => (
                        <GapItem
                          key={i}
                          gap={gap}
                          index={i}
                          onResolve={(answer) => gapResolveMut.mutate({ id: msg.id, gap_index: i, answer })}
                          isPending={gapResolveMut.isPending}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  {msg.status === 'pending_human' && (
                    <button
                      onClick={() => resolveMut.mutate(msg.id)}
                      disabled={resolveMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      <CheckCircle size={12} />
                      {resolveMut.isPending ? 'Resolving…' : 'Mark Resolved'}
                    </button>
                  )}
                  {msg.detected_product_name && (
                    <span className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-100 text-emerald-700 text-xs rounded-lg">
                      <Tag size={12} /> {msg.detected_product_name}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Analytics Tab ── */}
      {activeTab === 'analytics' && (
        <div className="flex-1 overflow-y-auto p-6">
          {!analyticsData ? (
            <div className="text-xs text-gray-400 text-center mt-16">Loading analytics…</div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-6">
              <h2 className="text-base font-semibold text-gray-900">WhatsApp Analytics</h2>

              {/* KPI Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: 'Total Messages', value: analyticsData.total_messages },
                  { label: 'Inbound',         value: analyticsData.total_inbound  },
                  { label: 'Sales Messages',  value: analyticsData.total_sales    },
                  { label: 'Auto-Sent Rate',  value: `${analyticsData.auto_sent_rate}%` },
                ].map(k => (
                  <div key={k.label} className="bg-white rounded-xl border border-gray-200 p-4">
                    <p className="text-xs text-gray-500">{k.label}</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{k.value}</p>
                  </div>
                ))}
              </div>

              {/* By Label */}
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-800 mb-3">Messages by Label</h3>
                <div className="space-y-2">
                  {Object.entries(analyticsData.by_label || {}).map(([label, count]) => {
                    const cfg = LABEL_CONFIG[label] || LABEL_CONFIG.Unclassified
                    const pct = analyticsData.total_messages > 0
                      ? Math.round(count / analyticsData.total_messages * 100) : 0
                    return (
                      <div key={label} className="flex items-center gap-3">
                        <span className={`text-xs w-24 ${cfg.text}`}>{label}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${cfg.dot}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 w-12 text-right">{count} ({pct}%)</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* By Status */}
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h3 className="text-sm font-semibold text-gray-800 mb-3">Pipeline Status</h3>
                <div className="grid grid-cols-3 gap-3">
                  {Object.entries(analyticsData.by_status || {}).map(([s, n]) => {
                    const cfg = STATUS_CONFIG[s]
                    const Icon = cfg?.icon || MessageSquare
                    return (
                      <div key={s} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
                        <Icon size={14} className={cfg?.color || 'text-gray-400'} />
                        <div>
                          <p className="text-xs text-gray-500 capitalize">{s.replace('_', ' ')}</p>
                          <p className="text-sm font-semibold text-gray-900">{n}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Settings Tab ── */}
      {activeTab === 'settings' && (
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">WhatsApp Accounts</h2>
              <button
                onClick={() => setAddFormOpen(v => !v)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#25D366] text-white text-xs font-medium rounded-lg hover:bg-[#128C7E]"
              >
                <Plus size={13} /> Connect Account
              </button>
            </div>

            {/* Add account form */}
            {addFormOpen && (
              <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
                <h3 className="text-sm font-semibold text-gray-800">Connect New WhatsApp Account</h3>
                {[
                  ['phone_number_id', 'Phone Number ID', 'From Meta → WhatsApp → API Setup'],
                  ['waba_id',         'WABA ID',         'WhatsApp Business Account ID'],
                  ['access_token',    'Permanent Access Token', 'System User token from Meta Business'],
                  ['verify_token',    'Webhook Verify Token', 'Your secret for webhook verification'],
                  ['display_phone',   'Display Phone Number', 'e.g. +919876543210'],
                  ['display_name',    'Display Name (optional)', 'e.g. RDL Technologies Sales'],
                ].map(([key, label, hint]) => (
                  <div key={key}>
                    <label className="text-xs font-medium text-gray-700">{label}</label>
                    <input
                      value={addForm[key]}
                      onChange={e => setAddForm(f => ({ ...f, [key]: e.target.value }))}
                      placeholder={hint}
                      type={key === 'access_token' ? 'password' : 'text'}
                      className="w-full mt-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#25D366]"
                    />
                  </div>
                ))}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={addForm.auto_send}
                    onChange={e => setAddForm(f => ({ ...f, auto_send: e.target.checked }))}
                    className="rounded text-[#25D366]"
                  />
                  <span className="text-xs text-gray-700">Enable Auto-Send (AI replies without human approval)</span>
                </label>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => {
                      addAccountMut.mutate(addForm, {
                        onSuccess: () => { setAddFormOpen(false); setAddForm({ phone_number_id:'',waba_id:'',access_token:'',verify_token:'',display_phone:'',display_name:'',auto_send:false }) }
                      })
                    }}
                    disabled={addAccountMut.isPending || !addForm.phone_number_id || !addForm.access_token || !addForm.verify_token}
                    className="px-4 py-1.5 bg-[#25D366] text-white text-xs font-medium rounded-lg hover:bg-[#128C7E] disabled:opacity-50"
                  >
                    {addAccountMut.isPending ? 'Connecting…' : 'Connect Account'}
                  </button>
                  <button
                    onClick={() => setAddFormOpen(false)}
                    className="px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Account list */}
            {accsLoading && <p className="text-xs text-gray-400">Loading accounts…</p>}
            {!accsLoading && (accountsData?.items || []).length === 0 && !addFormOpen && (
              <div className="text-center py-12 text-gray-400">
                <MessageCircle size={40} className="mx-auto mb-3 opacity-20" />
                <p className="text-sm">No WhatsApp accounts connected</p>
                <p className="text-xs mt-1">Click "Connect Account" to add your first WhatsApp Business number</p>
              </div>
            )}
            {(accountsData?.items || []).map(acct => (
              <div key={acct.id} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-[#25D366] flex items-center justify-center">
                      <Phone size={18} className="text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{acct.display_phone}</p>
                      <p className="text-xs text-gray-500">{acct.display_name || 'WhatsApp Business'}</p>
                      <p className="text-xs text-gray-400 mt-0.5">ID: {acct.phone_number_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {acct.is_primary && (
                      <span className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full">Primary</span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full ${acct.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                      {acct.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-100">
                  {/* Auto-send toggle */}
                  <button
                    onClick={() => toggleAutoSendMut.mutate({ id: acct.id, auto_send: !acct.auto_send })}
                    className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-gray-900"
                  >
                    {acct.auto_send
                      ? <ToggleRight size={16} className="text-[#25D366]" />
                      : <ToggleLeft size={16} className="text-gray-400" />}
                    Auto-Send: {acct.auto_send ? 'ON' : 'OFF'}
                  </button>
                  <div className="flex-1" />
                  {!acct.is_primary && (
                    <button
                      onClick={() => SetPrimaryWhatsAppAccountService(acct.id,
                        () => qc.invalidateQueries({ queryKey: ['wa-accounts'] }),
                        e => showToast(e, 'error')
                      )}
                      className="text-xs text-gray-500 hover:text-gray-700 underline"
                    >
                      Set Primary
                    </button>
                  )}
                  <button
                    onClick={() => {
                      if (confirm(`Remove ${acct.display_phone}?`)) deleteAccountMut.mutate(acct.id)
                    }}
                    className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700"
                  >
                    <Trash2 size={12} /> Remove
                  </button>
                </div>

                {/* Webhook URL hint */}
                <div className="mt-3 p-2 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500">
                    Webhook URL: <code className="text-xs bg-gray-200 px-1 rounded">/api/v1/whatsapp/webhook</code>
                    &nbsp;· Verify Token: <code className="text-xs bg-gray-200 px-1 rounded">••••••</code>
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Compose Modal ── */}
      {composeOpen && (
        <div className="fixed inset-0 bg-black/40 z-40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <Send size={14} className="text-[#25D366]" /> Send WhatsApp Message
              </h2>
              <button onClick={() => setComposeOpen(false)}>
                <X size={14} className="text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-700">From Account</label>
              <select
                value={composeData.account_id}
                onChange={e => setComposeData(d => ({ ...d, account_id: e.target.value }))}
                className="w-full mt-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#25D366]"
              >
                <option value="">Select account…</option>
                {(accountsData?.items || []).filter(a => a.is_active).map(a => (
                  <option key={a.id} value={a.id}>{a.display_phone} ({a.display_name || 'WhatsApp'})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-700">To (phone number)</label>
              <input
                value={composeData.to_number}
                onChange={e => setComposeData(d => ({ ...d, to_number: e.target.value }))}
                placeholder="+919876543210"
                className="w-full mt-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#25D366]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-gray-700">Message</label>
              <textarea
                value={composeData.body}
                onChange={e => setComposeData(d => ({ ...d, body: e.target.value }))}
                rows={4}
                placeholder="Type your message…"
                className="w-full mt-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-1 focus:ring-[#25D366]"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setComposeOpen(false)}
                className="px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => sendMut.mutate(composeData)}
                disabled={sendMut.isPending || !composeData.account_id || !composeData.to_number || !composeData.body}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-[#25D366] text-white text-xs font-medium rounded-lg hover:bg-[#128C7E] disabled:opacity-50"
              >
                <Send size={12} /> {sendMut.isPending ? 'Sending…' : 'Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Gap Item Component ─────────────────────────────────────────────────────────

function GapItem({ gap, index, onResolve, isPending }) {
  const [answer, setAnswer] = useState('')
  if (gap.resolved) {
    return (
      <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
        <p className="text-xs font-medium text-emerald-700">✓ Resolved: {gap.question}</p>
        <p className="text-xs text-gray-600 mt-1">{gap.answer}</p>
      </div>
    )
  }
  return (
    <div className="p-3 bg-white rounded-lg border border-red-200">
      <p className="text-xs font-semibold text-gray-800">{gap.question}</p>
      {gap.product_name && (
        <p className="text-xs text-gray-500 mt-0.5">Product: {gap.product_name}</p>
      )}
      <div className="flex gap-2 mt-2">
        <input
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          placeholder="Type the answer to add to knowledge base…"
          className="flex-1 text-xs px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-[#25D366]"
        />
        <button
          onClick={() => { onResolve(answer); setAnswer('') }}
          disabled={isPending || !answer.trim()}
          className="px-3 py-1.5 bg-[#25D366] text-white text-xs rounded hover:bg-[#128C7E] disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </div>
  )
}

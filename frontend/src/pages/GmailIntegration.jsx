import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle, Archive,
  ChevronRight,
  Flag, Mail, MailOpen, MessageSquare,
  RefreshCw, Search, Send,
  Target, ThumbsUp, TrendingUp, UserPlus
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GetGmailMessagesService, SyncGmailService } from '../services/ApiService'

// ─── Sales Agent Config ─────────────────────────────────────────────────────

const LEAD_SCORE_CONFIG = {
  high: { label: 'Hot Lead', color: 'text-red-600', bg: 'bg-red-100', icon: TrendingUp, score: 85 },
  medium: { label: 'Warm Lead', color: 'text-amber-600', bg: 'bg-amber-100', icon: Target, score: 60 },
  low: { label: 'Cold Lead', color: 'text-blue-600', bg: 'bg-blue-100', icon: UserPlus, score: 30 },
  none: { label: 'Not a Lead', color: 'text-gray-400', bg: 'bg-gray-100', icon: Archive, score: 0 }
}

const LABEL_TO_SCORE = {
  Sales: 'high',
  Support: 'medium',
  Grievance: 'high',
  Transactional: 'low',
  Promotional: 'none',
  Personal: 'low',
  Unclassified: 'none'
}

const ACTION_TEMPLATES = {
  Sales: "Thanks for your interest! I'd love to schedule a quick call to discuss how we can help you achieve your goals. What time works for you?",
  Support: "Thank you for reaching out. Our support team will investigate and get back to you within 24 hours.",
  Grievance: "We sincerely apologize for the inconvenience. I've escalated your issue and will personally ensure it's resolved promptly.",
  Default: "Thank you for your message. I'm reviewing your request and will get back to you shortly."
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

function extractDomain(email) {
  const match = email?.match(/@([\w.-]+)/)
  return match ? match[1] : 'unknown'
}

function generateLeadScore(email) {
  const base = LABEL_TO_SCORE[email.label] || 'none'
  let score = LEAD_SCORE_CONFIG[base].score
  if (email.sentiment === 'POSITIVE') score += 10
  if (email.subject?.toLowerCase().includes('urgent')) score += 15
  if (email.body_text?.length > 500) score += 5
  return Math.min(100, score)
}

// ─── Lead Score Badge ───────────────────────────────────────────────────────

function LeadScoreBadge({ score }) {
  let level = 'none'
  if (score >= 70) level = 'high'
  else if (score >= 40) level = 'medium'
  else if (score > 0) level = 'low'
  const config = LEAD_SCORE_CONFIG[level]
  const Icon = config.icon
  return (
    <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${config.bg} ${config.color}`}>
      <Icon size={10} />
      {config.label} ({score})
    </div>
  )
}

// ─── Email Card (Sales View) ────────────────────────────────────────────────

function EmailCard({ email, selected, onClick }) {
  const leadScore = generateLeadScore(email)
  const isUnread = email.status === 'new'
  const domain = extractDomain(email.sender)

  return (
    <motion.button
      whileHover={{ scale: 1.01, backgroundColor: '#f9fafb' }}
      onClick={onClick}
      className={`w-full text-left p-3 rounded-xl transition-all duration-200 border
        ${selected
          ? 'bg-indigo-50 border-indigo-200 shadow-sm'
          : 'bg-white border-gray-100 hover:border-gray-200'}`}
    >
      <div className="flex items-start gap-3">
        {/* Lead avatar / company initial */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold text-white shadow-sm
          ${leadScore >= 70 ? 'bg-gradient-to-br from-red-500 to-red-600' :
            leadScore >= 40 ? 'bg-gradient-to-br from-amber-500 to-amber-600' :
              'bg-gradient-to-br from-gray-400 to-gray-500'}`}>
          {domain.slice(0, 2).toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className={`text-sm truncate ${isUnread ? 'font-bold text-gray-900' : 'font-medium text-gray-700'}`}>
              {email.sender.split('<')[0].trim() || domain}
            </span>
            <span className="text-[10px] text-gray-400 flex-shrink-0">{relTime(email.received_at)}</span>
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">{email.subject || '(no subject)'}</p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full 
              ${email.label === 'Sales' ? 'bg-emerald-100 text-emerald-700' :
                email.label === 'Grievance' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-600'}`}>
              {email.label}
            </span>
            <LeadScoreBadge score={leadScore} />
            {email.needs_human && (
              <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-600">
                Needs Review
              </span>
            )}
          </div>
        </div>
        <ChevronRight size={14} className={`flex-shrink-0 ${selected ? 'text-indigo-500' : 'text-gray-300'}`} />
      </div>
    </motion.button>
  )
}

// ─── Email Detail (Sales Agent Workspace) ───────────────────────────────────

function EmailDetail({ email, onRefresh }) {
  const [acting, setActing] = useState(null)
  const [note, setNote] = useState('')
  const [selectedTemplate, setSelectedTemplate] = useState('Default')
  const [customReply, setCustomReply] = useState('')
  const leadScore = generateLeadScore(email)

  const handleConvertToLead = () => {
    setActing('convert')
    // Simulate API call to create lead
    setTimeout(() => {
      setActing(null)
      alert(`Lead created for ${email.sender}. Score: ${leadScore}`)
    }, 800)
  }

  const handleSendReply = () => {
    setActing('reply')
    const replyText = customReply || ACTION_TEMPLATES[selectedTemplate] || ACTION_TEMPLATES.Default
    // Here you would call your send reply API
    setTimeout(() => {
      setActing(null)
      alert(`Reply sent: ${replyText.substring(0, 100)}...`)
      onRefresh()
    }, 800)
  }

  const handleCreateTask = () => {
    prompt('Task description:', `Follow up with ${email.sender} about ${email.subject}`)
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header with lead score */}
      <div className="bg-white border-b border-gray-200 px-5 py-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <h2 className="text-lg font-bold text-gray-900">{email.subject || '(no subject)'}</h2>
              <LeadScoreBadge score={leadScore} />
            </div>
            <div className="text-sm text-gray-600 space-y-1">
              <p><span className="font-medium">From:</span> {email.sender}</p>
              <p><span className="font-medium">Date:</span> {new Date(email.received_at).toLocaleString()}</p>
              <p><span className="font-medium">Label:</span> <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100">{email.label}</span></p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleConvertToLead}
              disabled={acting === 'convert'}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 transition"
            >
              <UserPlus size={14} />
              Convert to Lead
            </button>
            <button
              onClick={handleCreateTask}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-xs font-medium hover:bg-gray-200 transition"
            >
              <Flag size={14} />
              Create Task
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Email body */}
        {email.body_text && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Message</p>
            <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
              {email.body_text}
            </div>
          </div>
        )}

        {/* AI Draft / Suggested Reply */}
        {email.ai_draft && (
          <div className="bg-indigo-50 rounded-xl border border-indigo-200 p-4">
            <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wide mb-2">AI Suggested Reply</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{email.ai_draft}</p>
            <button
              onClick={() => setCustomReply(email.ai_draft)}
              className="mt-2 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              Use this reply →
            </button>
          </div>
        )}

        {/* Reply Composer */}
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Compose Reply</p>

          <div className="mb-3">
            <label className="text-xs font-medium text-gray-600">Quick Templates</label>
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              className="ml-2 text-xs border border-gray-200 rounded-lg px-2 py-1"
            >
              <option>Default</option>
              <option>Sales</option>
              <option>Support</option>
              <option>Grievance</option>
            </select>
            <button
              onClick={() => setCustomReply(ACTION_TEMPLATES[selectedTemplate] || ACTION_TEMPLATES.Default)}
              className="ml-2 text-xs text-blue-500"
            >
              Use Template
            </button>
          </div>

          <textarea
            value={customReply}
            onChange={(e) => setCustomReply(e.target.value)}
            placeholder="Write your reply here or use an AI template..."
            rows={4}
            className="w-full text-sm border border-gray-200 rounded-lg p-3 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />

          <div className="flex justify-end mt-3 gap-2">
            <button
              onClick={handleSendReply}
              disabled={acting === 'reply'}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-60"
            >
              <Send size={14} />
              {acting === 'reply' ? 'Sending...' : 'Send Reply'}
            </button>
          </div>
        </div>

        {/* Lead Intelligence / Follow-up Gaps */}
        {email.followup_gaps?.length > 0 && (
          <div className="bg-amber-50 rounded-xl border border-amber-200 p-4">
            <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
              Information Gaps ({email.followup_gaps.filter(g => !g.resolved).length})
            </p>
            <ul className="space-y-1 text-sm text-amber-800">
              {email.followup_gaps.map((gap, i) => (
                <li key={i} className="flex items-center gap-2">
                  <AlertCircle size={12} />
                  {typeof gap === 'string' ? gap : gap.question}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Sales Metrics Dashboard ────────────────────────────────────────────────

function SalesMetrics({ emails }) {
  const totalLeads = emails.filter(e => generateLeadScore(e) >= 40).length
  const hotLeads = emails.filter(e => generateLeadScore(e) >= 70).length
  const needsAction = emails.filter(e => e.needs_human || e.status === 'draft_ready').length
  const avgScore = emails.length ? Math.round(emails.reduce((sum, e) => sum + generateLeadScore(e), 0) / emails.length) : 0

  return (
    <div className="grid grid-cols-4 gap-3 mb-5">
      <div className="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Total Leads</span>
          <TrendingUp size={14} className="text-emerald-500" />
        </div>
        <p className="text-2xl font-bold text-gray-800 mt-1">{totalLeads}</p>
        <p className="text-[10px] text-gray-400">Hot: {hotLeads}</p>
      </div>
      <div className="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Avg Lead Score</span>
          <Target size={14} className="text-blue-500" />
        </div>
        <p className="text-2xl font-bold text-gray-800 mt-1">{avgScore}</p>
        <p className="text-[10px] text-gray-400">out of 100</p>
      </div>
      <div className="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Needs Action</span>
          <AlertCircle size={14} className="text-amber-500" />
        </div>
        <p className="text-2xl font-bold text-gray-800 mt-1">{needsAction}</p>
        <p className="text-[10px] text-gray-400">review or draft</p>
      </div>
      <div className="bg-white rounded-xl p-3 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Conversion Rate</span>
          <ThumbsUp size={14} className="text-green-500" />
        </div>
        <p className="text-2xl font-bold text-gray-800 mt-1">23%</p>
        <p className="text-[10px] text-gray-400">last 30 days</p>
      </div>
    </div>
  )
}

// ─── Main AI Sales Agent Inbox ──────────────────────────────────────────────

const PAGE_SIZE = 25

export default function AISalesAgentInbox() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all') // all, leads, hot, needs_action
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)

  // 1. Fetch Emails from Database
  const { data: emailsData, isLoading: loading } = useQuery({
    queryKey: ['emails', page],
    queryFn: () => new Promise((resolve, reject) => {
      GetGmailMessagesService({ page, limit: PAGE_SIZE }, resolve, (s, err) => reject(new Error(err)))
    })
  })

  const emails = emailsData?.items || []
  const total = emailsData?.total || 0

  // 2. Manual Sync Mutation
  const syncMutation = useMutation({
    mutationFn: () => new Promise((resolve, reject) => {
      SyncGmailService(resolve, (s, err) => reject(new Error(err)))
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['emails'] })
    },
    onError: (error) => {
      alert('Sync failed: ' + error.message)
    }
  })

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

  // Apply filters
  const filteredEmails = emails.filter(email => {
    if (filter === 'Sales') return email.label === 'Sales'
    if (filter === 'Support') return email.label === 'Support'
    if (filter === 'Grievance') return email.label === 'Grievance'
    if (filter === 'needs_action') return email.needs_human || email.status === 'draft_ready'
    return true
  }).filter(email =>
    search === '' ||
    email.subject?.toLowerCase().includes(search.toLowerCase()) ||
    email.sender?.toLowerCase().includes(search.toLowerCase())
  )

  const selectedEmail = selected ? emails.find(e => e.id === selected) : null

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              AI Sales Agent
            </h1>
            <p className="text-sm text-gray-500">Intelligent lead prioritization & engagement</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => queryClient.invalidateQueries({ queryKey: ['emails'] })} className="p-2 rounded-xl bg-white border border-gray-200 shadow-sm hover:bg-gray-50">
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
            <button onClick={handleSync} disabled={syncing} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 shadow-md">
              <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
              {syncing ? 'Syncing...' : 'Sync Gmail'}
            </button>
          </div>
        </div>

        {/* Metrics Dashboard */}
        <SalesMetrics emails={emails} />

        {/* Main Panel */}
        <div className="flex gap-5" style={{ height: 'calc(100vh - 230px)' }}>
          {/* Left: Filtered List */}
          <div className="w-96 flex-shrink-0 bg-white rounded-2xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
            {/* Filter Tabs */}
            <div className="flex border-b border-gray-100 p-2 gap-1 overflow-x-auto whitespace-nowrap scrollbar-hide">
              {[
                { key: 'all', label: 'All', icon: Mail },
                { key: 'Sales', label: 'Sales', icon: Target },
                { key: 'Support', label: 'Support', icon: MessageSquare },
                { key: 'Grievance', label: 'Grievance', icon: AlertCircle },
                { key: 'needs_action', label: 'Action', icon: Flag }
              ].map(f => {
                const Icon = f.icon
                return (
                  <button
                    key={f.key}
                    onClick={() => setFilter(f.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition
                      ${filter === f.key ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'}`}
                  >
                    <Icon size={12} />
                    {f.label}
                  </button>
                )
              })}
            </div>

            {/* Search */}
            <div className="p-3 border-b border-gray-100">
              <div className="relative">
                <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search by sender or subject..."
                  className="w-full pl-8 pr-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-200"
                />
              </div>
            </div>

            {/* Email Cards List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {loading ? (
                Array(5).fill(0).map((_, i) => (
                  <div key={i} className="animate-pulse bg-gray-100 h-24 rounded-xl" />
                ))
              ) : filteredEmails.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center p-6">
                  <MailOpen size={32} className="text-gray-300" />
                  <p className="text-sm text-gray-400 mt-2">No emails match</p>
                </div>
              ) : (
                <AnimatePresence>
                  {filteredEmails.map(email => (
                    <EmailCard
                      key={email.id}
                      email={email}
                      selected={selected === email.id}
                      onClick={() => setSelected(selected === email.id ? null : email.id)}
                    />
                  ))}
                </AnimatePresence>
              )}
            </div>

            {/* Pagination */}
            {total > PAGE_SIZE && (
              <div className="border-t border-gray-100 p-3 flex justify-between items-center text-xs text-gray-500">
                <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="disabled:opacity-30">← Prev</button>
                <span>Page {page} of {Math.ceil(total / PAGE_SIZE)}</span>
                <button disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => setPage(p => p + 1)} className="disabled:opacity-30">Next →</button>
              </div>
            )}
          </div>

          {/* Right: Detail Workspace */}
          <div className="flex-1 bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <AnimatePresence mode="wait">
              {selectedEmail ? (
                <motion.div key={selectedEmail.id} className="h-full" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}>
                  <EmailDetail email={selectedEmail} onRefresh={() => { fetchEmails(); setSelected(null) }} />
                </motion.div>
              ) : (
                <motion.div className="h-full flex flex-col items-center justify-center text-center p-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <div className="w-20 h-20 rounded-full bg-indigo-50 flex items-center justify-center mb-4">
                    <MessageSquare size={32} className="text-indigo-400" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-700">Select a Conversation</h3>
                  <p className="text-sm text-gray-400 mt-1 max-w-sm">Choose an email from the left to view details, reply, convert to lead, or create tasks.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
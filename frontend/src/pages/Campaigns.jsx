import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Megaphone, Plus, Edit2, Trash2, Play, Pause, Users,
  Send, MessageSquare, CheckCircle, X, Zap, Target, ToggleLeft, ToggleRight
} from 'lucide-react'
import {
  GetCampaignsService, CreateCampaignService, UpdateCampaignService,
  DeleteCampaignService, GenerateDraftsService, GetEmailAccountsService,
} from '../services/ApiService'

const STATUS_CONFIG = {
  draft:     { color: '#9ca3af', bg: 'bg-gray-100 text-gray-600',    label: 'Draft' },
  active:    { color: '#10b981', bg: 'bg-emerald-100 text-emerald-700', label: 'Active' },
  paused:    { color: '#f59e0b', bg: 'bg-amber-100 text-amber-700',   label: 'Paused' },
  completed: { color: '#6172f3', bg: 'bg-indigo-100 text-indigo-700', label: 'Completed' },
}

const EMPTY_FORM = {
  name: '', target_industry: '', target_roles_str: '',
  auto_send: false, email_template_prompt: '',
  product_context: '', email_subject: '', assigned_account_id: '',
}

function CampaignForm({ initial, onSave, onClose }) {
  const [form, setForm] = useState(initial || EMPTY_FORM)
  const [accounts, setAccounts] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    GetEmailAccountsService(d => setAccounts(d?.items || []), () => {})
  }, [])

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const handleSave = () => {
    if (!form.name.trim()) return
    setSaving(true)
    const payload = {
      ...form,
      target_roles: form.target_roles_str ? form.target_roles_str.split(',').map(r => r.trim()).filter(Boolean) : [],
      assigned_account_id: form.assigned_account_id || undefined,
    }
    delete payload.target_roles_str
    onSave(payload, () => setSaving(false))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100 sticky top-0 bg-white z-10">
          <h3 className="text-base font-bold text-gray-900">{initial?.id ? 'Edit Campaign' : 'New Campaign'}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Campaign Name *</label>
            <input value={form.name} onChange={e => f('name', e.target.value)} placeholder="e.g. Manufacturing Outreach Q3"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Target Industry</label>
              <input value={form.target_industry} onChange={e => f('target_industry', e.target.value)} placeholder="e.g. manufacturing"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Target Roles <span className="text-gray-400">(comma-separated)</span></label>
              <input value={form.target_roles_str} onChange={e => f('target_roles_str', e.target.value)} placeholder="e.g. Plant Manager, CTO"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Email Subject Line</label>
            <input value={form.email_subject} onChange={e => f('email_subject', e.target.value)} placeholder="e.g. Improve your plant efficiency with RDL IoT solutions"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">AI Template Guidance</label>
            <textarea value={form.email_template_prompt} onChange={e => f('email_template_prompt', e.target.value)} rows={3}
              placeholder="Describe the tone and focus: e.g. 'Focus on ROI and quick deployment. Be direct and solution-oriented.'"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white resize-none" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-600 block mb-1">Product Context</label>
            <textarea value={form.product_context} onChange={e => f('product_context', e.target.value)} rows={3}
              placeholder="Describe your products/services to help AI personalize messages. e.g. 'We make industrial IoT data loggers and PLCs for factory automation...'"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white resize-none" />
          </div>
          {accounts.length > 1 && (
            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">Send From Account</label>
              <select value={form.assigned_account_id} onChange={e => f('assigned_account_id', e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white">
                <option value="">Default (primary account)</option>
                {accounts.map(a => <option key={a.id} value={a.id}>{a.email_address}</option>)}
              </select>
            </div>
          )}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div>
              <p className="text-sm font-semibold text-gray-900">Auto-Send Mode</p>
              <p className="text-xs text-gray-400 mt-0.5">AI sends messages automatically without human approval</p>
            </div>
            <button onClick={() => f('auto_send', !form.auto_send)}
              className={`flex-shrink-0 transition-colors ${form.auto_send ? 'text-indigo-600' : 'text-gray-400'}`}>
              {form.auto_send ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
            </button>
          </div>
        </div>
        <div className="px-6 pb-5 flex gap-3">
          <button onClick={onClose} className="flex-1 h-10 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={handleSave} disabled={saving || !form.name.trim()}
            className="flex-1 h-10 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 transition-all">
            {saving ? 'Saving…' : 'Save Campaign'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editTarget, setEditTarget] = useState(null)
  const [generatingId, setGeneratingId] = useState(null)

  const load = () => {
    setLoading(true)
    GetCampaignsService(d => { setCampaigns(d || []); setLoading(false) }, () => setLoading(false))
  }
  useEffect(load, [])

  const handleSave = (payload, done) => {
    if (editTarget?.id) {
      UpdateCampaignService(editTarget.id, payload, () => { load(); setShowForm(false); setEditTarget(null); done() }, done)
    } else {
      CreateCampaignService(payload, () => { load(); setShowForm(false); done() }, done)
    }
  }

  const handleDelete = (id) => {
    if (!confirm('Delete this campaign? All contact records will also be removed.')) return
    DeleteCampaignService(id, load, () => {})
  }

  const handleToggleStatus = (c) => {
    const next = c.status === 'active' ? 'paused' : 'active'
    UpdateCampaignService(c.id, { status: next }, load, () => {})
  }

  const handleGenerateDrafts = (id) => {
    setGeneratingId(id)
    GenerateDraftsService(id, res => { setGeneratingId(null); alert(`Generated ${res.drafts_generated} AI drafts`) }, () => setGeneratingId(null))
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black text-gray-900">Outreach Campaigns</h1>
            <p className="text-xs text-gray-400 mt-0.5">Create and manage AI-powered email outreach campaigns</p>
          </div>
          <button onClick={() => { setEditTarget(null); setShowForm(true) }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-all shadow-md shadow-indigo-200">
            <Plus size={16} /> New Campaign
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1,2,3].map(i => <div key={i} className="h-52 rounded-2xl bg-white border border-gray-100 animate-pulse" />)}
          </div>
        ) : campaigns.length === 0 ? (
          <div className="text-center py-24">
            <Megaphone size={40} className="mx-auto text-gray-200 mb-3" />
            <p className="text-base font-bold text-gray-400">No campaigns yet</p>
            <p className="text-sm text-gray-400 mt-1">Create your first outreach campaign to get started</p>
            <button onClick={() => { setEditTarget(null); setShowForm(true) }}
              className="mt-5 px-6 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700">
              Create Campaign
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {campaigns.map(c => {
              const cfg = STATUS_CONFIG[c.status] || STATUS_CONFIG.draft
              return (
                <motion.div key={c.id} layout className="bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow p-5">
                  <div className="flex items-start justify-between gap-2 mb-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-wide ${cfg.bg}`}>{cfg.label}</span>
                        {c.auto_send && <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">AUTO</span>}
                      </div>
                      <h3 className="text-sm font-black text-gray-900 truncate">{c.name}</h3>
                      {c.target_industry && <p className="text-xs text-gray-400 mt-0.5">{c.target_industry}</p>}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button onClick={() => { setEditTarget(c); setShowForm(true) }} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700">
                        <Edit2 size={13} />
                      </button>
                      <button onClick={() => handleDelete(c.id)} className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    {[
                      { icon: Users, label: 'Contacts', val: c.contact_count, color: '#6172f3' },
                      { icon: Send, label: 'Sent', val: c.sent_count, color: '#10b981' },
                      { icon: MessageSquare, label: 'Replied', val: c.replied_count, color: '#f59e0b' },
                    ].map(({ icon: Icon, label, val, color }) => (
                      <div key={label} className="text-center p-2 rounded-xl bg-gray-50">
                        <p className="text-lg font-black" style={{ color }}>{val}</p>
                        <p className="text-[9px] font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
                      </div>
                    ))}
                  </div>

                  {/* Role tags */}
                  {c.target_roles?.length > 0 && (
                    <div className="flex gap-1 flex-wrap mb-4">
                      {c.target_roles.slice(0, 3).map(r => (
                        <span key={r} className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600">{r}</span>
                      ))}
                      {c.target_roles.length > 3 && <span className="text-[10px] text-gray-400">+{c.target_roles.length - 3}</span>}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2">
                    <button onClick={() => handleToggleStatus(c)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${c.status === 'active' ? 'bg-amber-50 text-amber-700 hover:bg-amber-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'}`}>
                      {c.status === 'active' ? <><Pause size={11} />Pause</> : <><Play size={11} />Activate</>}
                    </button>
                    <button onClick={() => handleGenerateDrafts(c.id)} disabled={generatingId === c.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-all disabled:opacity-50">
                      <Zap size={11} className={generatingId === c.id ? 'animate-pulse' : ''} />
                      {generatingId === c.id ? 'Generating…' : 'AI Drafts'}
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      <AnimatePresence>
        {showForm && (
          <CampaignForm
            initial={editTarget ? { ...editTarget, target_roles_str: (editTarget.target_roles || []).join(', ') } : null}
            onSave={handleSave}
            onClose={() => { setShowForm(false); setEditTarget(null) }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

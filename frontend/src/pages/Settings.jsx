import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell, Cpu, Key, Save, Mail, Plus,
  Trash2, Star, AlertCircle, RefreshCw, ToggleLeft, ToggleRight,
  Download
} from 'lucide-react'
import {
  GetEmailAccountsService, GetEmailAccountAuthUrlService,
  UpdateEmailAccountService, SetPrimaryEmailAccountService, DeleteEmailAccountService,
  GetCurrentUserService,
} from '../services/ApiService'

// ─── Static settings sections (unchanged) ────────────────────────────────────

const staticSections = [
  {
    icon: Cpu, title: 'AI Configuration', color: '#6172f3',
    fields: [
      { label: 'AI Model',               type: 'select',  options: ['Gemini 2.5 Flash', 'Gemini 2.0 Flash', 'Claude 3.5 Sonnet'], value: 'Gemini 2.5 Flash' },
      { label: 'Max Calls Per Hour',      type: 'number',  value: '120' },
      { label: 'AI Tone',                 type: 'select',  options: ['Professional', 'Friendly', 'Formal'], value: 'Professional' },
      { label: 'Auto-retry Failed Calls', type: 'toggle',  value: true },
    ]
  },
  {
    icon: Bell, title: 'Notifications', color: '#f59e0b',
    fields: [
      { label: 'Email Alerts',        type: 'toggle', value: true },
      { label: 'Slack Webhook URL',   type: 'text',   value: 'https://hooks.slack.com/...' },
      { label: 'New Lead Alert',      type: 'toggle', value: true },
      { label: 'Call Summary Digest', type: 'select', options: ['Daily', 'Weekly', 'Off'], value: 'Daily' },
    ]
  },
  // {
  //   icon: Shield, title: 'Security', color: '#10b981',
  //   fields: [
  //     { label: 'Two-Factor Auth',           type: 'toggle', value: true },
  //     { label: 'Session Timeout (minutes)', type: 'number', value: '60' },
  //     { label: 'API Rate Limiting',         type: 'toggle', value: true },
  //     { label: 'Data Encryption',           type: 'toggle', value: true },
  //   ]
  // },
]

function Toggle({ value }) {
  return (
    <div className={`relative w-10 h-5 rounded-full transition-all cursor-pointer ${value ? 'bg-blue-600' : 'bg-gray-200'}`}>
      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${value ? 'left-5' : 'left-0.5'}`} />
    </div>
  )
}

// ─── Email Accounts Section ───────────────────────────────────────────────────

function AccountBadge({ is_primary, is_active }) {
  if (is_primary) return (
    <span className="inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
      <Star size={9} /> Primary
    </span>
  )
  if (!is_active) return (
    <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-400">Inactive</span>
  )
  return <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Active</span>
}

function EmailAccountsSection() {
  const location = useLocation()
  const [accounts, setAccounts] = useState([])
  const [me, setMe] = useState(null)
  const [loading, setLoading] = useState(true)
  const [authLoading, setAuthLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [acting, setActing] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  const fetchAccounts = () => {
    setLoading(true)
    GetEmailAccountsService(
      (data) => { setAccounts(data?.items || []); setLoading(false) },
      () => setLoading(false)
    )
  }

  useEffect(() => {
    fetchAccounts()
    GetCurrentUserService((data) => setMe(data), () => {})
    const params = new URLSearchParams(location.search)
    if (params.get('email_added')) showToast(`✓ ${params.get('email_added')} connected successfully`)
    if (params.get('email_error')) showToast('Failed to connect account — please try again', 'error')
  }, [location.search])

  const handleAddAccount = () => {
    // Super-admins can connect any number of accounts; regular users are capped at
    // one of THEIR OWN (mirrors the backend rule in exchange_code_and_save). A
    // super-admin sees every account in the system here, so counting the whole
    // list — instead of just the ones they themselves own — would wrongly block
    // them from adding a second account the moment any other user has one.
    const ownAccounts = me ? accounts.filter(a => a.owner_id === me.id) : []
    if (!me?.is_superuser && ownAccounts.length >= 1) {
      showToast('You already have a Gmail account connected. Remove it before adding a new one.', 'error')
      return
    }
    setAuthLoading(true)
    GetEmailAccountAuthUrlService(
      (data) => { window.location.href = data.url },
      (_status, msg) => { setAuthLoading(false); showToast(msg || 'Could not get auth URL', 'error') }
    )
  }

  const handleToggleActive = (acct) => {
    // Confirm before deactivating — deactivated accounts stop being polled for new emails
    if (acct.is_active && !window.confirm(`Deactivate ${acct.email_address}?\n\nThis stops the poller from checking this inbox for new emails.`)) return
    setActing(acct.id + '_toggle')
    UpdateEmailAccountService(acct.id, { is_active: !acct.is_active },
      () => { fetchAccounts(); setActing(null); showToast(`${acct.email_address} ${acct.is_active ? 'deactivated — polling stopped' : 'activated — polling resumed'}`) },
      () => { setActing(null); showToast('Update failed', 'error') }
    )
  }

  // Re-run the OAuth consent flow for an already-connected account so it can
  // pick up scopes (e.g. Calendar) granted after the account first connected.
  // The callback matches on email address and refreshes the existing row
  // rather than creating a duplicate, so this is safe to call anytime.
  const handleReconnect = (acct) => {
    setActing(acct.id + '_reconnect')
    GetEmailAccountAuthUrlService(
      (data) => { window.location.href = data.url },
      (_status, msg) => { setActing(null); showToast(msg || 'Could not get auth URL', 'error') }
    )
  }

  const handleSetPrimary = (acct) => {
    setActing(acct.id + '_primary')
    SetPrimaryEmailAccountService(acct.id,
      () => { fetchAccounts(); setActing(null); showToast(`${acct.email_address} set as primary`) },
      () => { setActing(null); showToast('Failed', 'error') }
    )
  }

  const handleDelete = (acct) => {
    if (!window.confirm(`Remove ${acct.email_address}? Existing emails will be kept.`)) return
    setActing(acct.id + '_del')
    DeleteEmailAccountService(acct.id,
      () => { fetchAccounts(); setActing(null); showToast(`${acct.email_address} removed`) },
      () => { setActing(null); showToast('Delete failed', 'error') }
    )
  }

  const handleSyncHistory = (acct) => {
    if (!window.confirm(`Import last 30 days of emails from ${acct.email_address}?\nThis runs in the background and may take a few minutes.`)) return
    setActing(acct.id + '_sync')
    fetch(`/api/v1/settings/email-accounts/${acct.id}/sync-history?days=30`, { method: 'POST', credentials: 'include' })
      .then(r => r.json())
      .then(() => { setActing(null); showToast(`Syncing ${acct.email_address} history in background…`) })
      .catch(() => { setActing(null); showToast('Sync failed', 'error') })
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className={`fixed top-20 right-5 z-50 px-4 py-2.5 rounded-xl text-xs font-semibold shadow-lg
              ${toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="flex items-center justify-between mb-5 pb-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl" style={{ background: '#10b98120' }}>
            <Mail size={16} style={{ color: '#10b981' }} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Gmail Accounts</h3>
            <p className="text-[11px] text-gray-400 mt-0.5">{accounts.length} account{accounts.length !== 1 ? 's' : ''} configured — all active accounts are polled</p>
          </div>
        </div>
        <button onClick={handleAddAccount} disabled={authLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-all disabled:opacity-60">
          {authLoading
            ? <RefreshCw size={12} className="animate-spin" />
            : <Plus size={12} />}
          {authLoading ? 'Redirecting...' : 'Add Account'}
        </button>
      </div>

      {/* Account list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2].map(i => <div key={i} className="h-16 rounded-xl bg-gray-100 animate-pulse" />)}
        </div>
      ) : accounts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
          <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center">
            <Mail size={20} className="text-blue-400" />
          </div>
          <p className="text-sm font-semibold text-gray-700">No Gmail accounts connected</p>
          <p className="text-xs text-gray-400 max-w-xs">
            Click <strong>Add Account</strong> to connect a Gmail account via Google OAuth.
            You can add up to 5+ accounts — all will be polled for incoming emails.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map(acct => (
            <div key={acct.id}
              className={`flex items-center gap-4 px-4 py-3 rounded-xl border transition-all
                ${acct.is_primary ? 'border-amber-200 bg-amber-50/40' :
                  acct.is_active ? 'border-emerald-100 bg-emerald-50/20' :
                  'border-gray-100 bg-gray-50'}`}>
              {/* Avatar */}
              <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0
                ${acct.is_primary ? 'bg-amber-500' : acct.is_active ? 'bg-emerald-500' : 'bg-gray-400'}`}>
                {acct.email_address[0].toUpperCase()}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-gray-900 truncate">{acct.email_address}</span>
                  <AccountBadge is_primary={acct.is_primary} is_active={acct.is_active} />
                </div>
                {acct.display_name && acct.display_name !== acct.email_address && (
                  <p className="text-[11px] text-gray-400 mt-0.5">{acct.display_name}</p>
                )}
                {!(acct.scopes || []).includes('https://www.googleapis.com/auth/calendar.events') && (
                  <p className="text-[11px] text-amber-600 mt-0.5">
                    No Calendar access — meetings for this rep&apos;s leads are skipped and flagged for manual scheduling. Reconnect to fix.
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {/* Reconnect (refresh token/scopes) */}
                <button
                  onClick={() => handleReconnect(acct)}
                  disabled={!!acting}
                  title="Reconnect — refreshes token and picks up newly added scopes (e.g. Calendar)"
                  className="p-1.5 rounded-lg text-indigo-400 hover:bg-indigo-50 transition-all disabled:opacity-50">
                  {acting === acct.id + '_reconnect' ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                </button>

                {/* Auto-send toggle */}
                <button
                  onClick={() => {
                    const sending = !acct.auto_send_enabled
                    console.log('[AUTO-SEND TOGGLE] click', { acct_id: acct.id, email: acct.email_address, current: acct.auto_send_enabled, sending_new_value: sending })
                    setActing(acct.id + '_autosend')
                    UpdateEmailAccountService(acct.id, { auto_send_enabled: sending },
                      (resp) => {
                        console.log('[AUTO-SEND TOGGLE] PATCH success — server response:', resp)
                        // Refetch and log what GET returns
                        GetEmailAccountsService(
                          (data) => {
                            const updated = (data?.items || []).find(x => x.id === acct.id)
                            console.log('[AUTO-SEND TOGGLE] GET refetch — server now says auto_send_enabled =', updated?.auto_send_enabled, 'for', updated?.email_address)
                            setAccounts(data?.items || [])
                            setActing(null)
                            showToast(`Auto-send ${sending ? 'enabled' : 'disabled'} for ${acct.email_address}`)
                          },
                          (status, msg) => { console.warn('[AUTO-SEND TOGGLE] GET refetch FAILED', status, msg); setActing(null) }
                        )
                      },
                      (status, msg) => { console.error('[AUTO-SEND TOGGLE] PATCH FAILED', status, msg); setActing(null); showToast('Update failed', 'error') }
                    )
                  }}
                  disabled={!!acting}
                  title={acct.auto_send_enabled ? 'Auto-send ON — click to require manual approval' : 'Auto-send OFF — click to enable'}
                  className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold transition-all disabled:opacity-50
                    ${acct.auto_send_enabled ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-amber-100 text-amber-700 hover:bg-amber-200'}`}>
                  {acct.auto_send_enabled ? '⚡ Auto' : '✋ Draft'}
                </button>

                {/* Toggle active */}
                <button
                  onClick={() => handleToggleActive(acct)}
                  disabled={!!acting}
                  title={acct.is_active ? 'Deactivate' : 'Activate'}
                  className={`p-1.5 rounded-lg transition-all disabled:opacity-50
                    ${acct.is_active ? 'text-emerald-600 hover:bg-emerald-50' : 'text-gray-400 hover:bg-gray-100'}`}>
                  {acct.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                </button>

                {/* Set primary */}
                {!acct.is_primary && (
                  <button
                    onClick={() => handleSetPrimary(acct)}
                    disabled={!!acting}
                    title="Set as primary"
                    className="p-1.5 rounded-lg text-amber-500 hover:bg-amber-50 transition-all disabled:opacity-50">
                    <Star size={14} />
                  </button>
                )}

                {/* Sync history */}
                <button
                  onClick={() => handleSyncHistory(acct)}
                  disabled={!!acting}
                  title="Import last 30 days of emails"
                  className="p-1.5 rounded-lg text-blue-400 hover:bg-blue-50 transition-all disabled:opacity-50">
                  {acting === acct.id + '_sync' ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
                </button>

                {/* Remove */}
                <button
                  onClick={() => handleDelete(acct)}
                  disabled={!!acting}
                  title="Remove account"
                  className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 transition-all disabled:opacity-50">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info note */}
      {accounts.length > 0 && (
        <p className="mt-4 text-[11px] text-gray-400 flex items-center gap-1.5">
          <AlertCircle size={11} />
          All <strong>active</strong> accounts are polled every 2 minutes.
          The <strong>primary</strong> account is used for outbound emails by default.
        </p>
      )}
    </motion.div>
  )
}

// ─── Main Settings page ───────────────────────────────────────────────────────

export default function Settings() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5 max-w-4xl">

      {/* Email Accounts — live section */}
      <EmailAccountsSection />

      {/* Static config sections */}
      {staticSections.map((section, si) => (
        <motion.div key={si} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: si * 0.06 }}
          className="glass-card p-6">
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-200">
            <div className="p-2 rounded-xl" style={{ background: `${section.color}20` }}>
              <section.icon size={16} style={{ color: section.color }} />
            </div>
            <h3 className="text-sm font-semibold text-gray-900">{section.title}</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {section.fields.map((field, fi) => (
              <div key={fi} className="flex items-center justify-between p-3.5 rounded-xl bg-gray-50 border border-gray-200">
                <label className="text-xs text-gray-600 font-medium">{field.label}</label>
                {field.type === 'toggle' ? (
                  <Toggle value={field.value} />
                ) : field.type === 'select' ? (
                  <select className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500">
                    {field.options.map(o => <option key={o}>{o}</option>)}
                  </select>
                ) : field.type === 'password' ? (
                  <div className="relative">
                    <Key size={10} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input type="password" defaultValue={field.value}
                      className="text-xs bg-white border border-gray-200 rounded-lg pl-5 pr-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500 w-36" />
                  </div>
                ) : (
                  <input type={field.type} defaultValue={field.value}
                    className="text-xs bg-white border border-gray-200 rounded-lg px-2 py-1 text-gray-900 focus:outline-none focus:border-blue-500 w-28 text-right" />
                )}
              </div>
            ))}
          </div>
        </motion.div>
      ))}

      <div className="flex justify-end">
        <button className="btn-primary flex items-center gap-2">
          <Save size={14} />
          Save All Settings
        </button>
      </div>
    </motion.div>
  )
}

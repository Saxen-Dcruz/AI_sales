import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Building2, Users, Globe, MapPin, Briefcase, Star,
  ChevronRight, Plus, Filter, RefreshCw, Zap, CheckCircle,
  ExternalLink, Tag, X, Target, Linkedin, Loader2,
} from 'lucide-react'
import {
  RunDiscoverySearchService, GetProspectCompaniesService,
  GetProspectContactsService, ScoreCompaniesService,
  GetCampaignsService, AddContactsToCampaignService,
  RunLinkedInScrapeService,
} from '../services/ApiService'

const SIZES = ['1-10','11-50','51-200','201-500','500+']
const SCORE_COLOR = s => s >= 70 ? '#10b981' : s >= 40 ? '#f59e0b' : '#ef4444'
const LEVEL_BADGE = { hot: 'bg-red-100 text-red-700', warm: 'bg-amber-100 text-amber-700', cold: 'bg-blue-100 text-blue-700' }

function ScoreBadge({ score, level }) {
  if (score == null) return <span className="text-[10px] text-gray-400">—</span>
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black text-white"
        style={{ background: SCORE_COLOR(score) }}>
        {score}
      </div>
      {level && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${LEVEL_BADGE[level] || 'bg-gray-100 text-gray-500'}`}>{level}</span>}
    </div>
  )
}

function AddToCampaignModal({ selectedContacts, onClose, onSuccess }) {
  const [campaigns, setCampaigns] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    GetCampaignsService(d => setCampaigns(d || []), () => {})
  }, [])

  const handleAdd = () => {
    if (!selected) return
    setLoading(true)
    AddContactsToCampaignService(selected, selectedContacts.map(c => c.id),
      res => { setLoading(false); onSuccess(res.added) },
      () => setLoading(false)
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-bold text-gray-900">Add {selectedContacts.length} contact{selectedContacts.length !== 1 ? 's' : ''} to campaign</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>
        </div>
        <div className="space-y-2 max-h-64 overflow-y-auto mb-5">
          {campaigns.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">No campaigns yet. Create one first.</p>
          ) : campaigns.map(c => (
            <button key={c.id} onClick={() => setSelected(c.id)}
              className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${selected === c.id ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}`}>
              <p className="text-sm font-semibold text-gray-900">{c.name}</p>
              <p className="text-xs text-gray-400 mt-0.5">{c.contact_count} contacts · {c.status}</p>
            </button>
          ))}
        </div>
        <button onClick={handleAdd} disabled={!selected || loading}
          className="w-full h-10 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50 hover:bg-indigo-700 transition-all">
          {loading ? 'Adding…' : 'Add to Campaign'}
        </button>
      </motion.div>
    </div>
  )
}

const LOADING_STEPS = [
  'Launching browser…',
  'Connecting to LinkedIn…',
  'Scanning profiles…',
  'Extracting data…',
]

function ModalLoadingView({ keyword }) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setStep(s => (s + 1) % LOADING_STEPS.length), 1200)
    return () => clearInterval(t)
  }, [])

  return (
    <motion.div
      key="loading"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="flex flex-col items-center gap-5 py-8 px-6"
      style={{ background: 'linear-gradient(160deg, #003d6b 0%, #0077b5 100%)', borderRadius: '0 0 1rem 1rem' }}
    >
      {/* Pulsing LinkedIn icon with ring */}
      <div className="relative">
        <motion.div
          animate={{ scale: [1, 1.12, 1], boxShadow: ['0 0 0 0 rgba(255,255,255,0.25)', '0 0 0 16px rgba(255,255,255,0)', '0 0 0 0 rgba(255,255,255,0)'] }}
          transition={{ duration: 1.6, repeat: Infinity }}
          className="w-16 h-16 rounded-2xl flex items-center justify-center border-2 border-white/30 bg-white/15"
        >
          <Linkedin size={30} className="text-white" />
        </motion.div>
        {/* Orbiting dot */}
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 2.4, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-amber-400 border-2 border-white" />
        </motion.div>
      </div>

      {/* Label */}
      <div className="text-center">
        <p className="text-white font-black text-base">Bot is scraping LinkedIn…</p>
        <p className="text-white/60 text-xs mt-1">
          Searching for <span className="text-white font-semibold">"{keyword}"</span>
        </p>
      </div>

      {/* Equalizer bars */}
      <div className="flex items-end gap-1 h-8">
        {[0.4, 0.8, 1, 0.55, 0.9, 0.45, 0.75, 0.6].map((h, i) => (
          <motion.div key={i}
            className="w-2 rounded-full bg-white/50"
            style={{ originY: 1 }}
            animate={{ scaleY: [h, 1, h] }}
            transition={{ duration: 0.55 + i * 0.06, delay: i * 0.07, repeat: Infinity, ease: 'easeInOut' }}
          />
        ))}
      </div>

      {/* Cycling step text */}
      <AnimatePresence mode="wait">
        <motion.p
          key={step}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.3 }}
          className="text-white/80 text-xs font-medium"
        >
          {LOADING_STEPS[step]}
        </motion.p>
      </AnimatePresence>

      {/* Sweeping progress bar */}
      <div className="w-full h-1 rounded-full bg-white/20 overflow-hidden">
        <motion.div
          className="h-full w-1/3 rounded-full bg-white"
          animate={{ x: ['-100%', '400%'] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>
    </motion.div>
  )
}

function LinkedInScrapeModal({ onClose, onStarted }) {
  const [form, setForm] = useState({ keyword: '', location: 'India', target_roles: 'Manager,Director,CEO,Operations,Procurement', max_companies: 10, max_people: 5 })
  const [loading, setLoading] = useState(false)
  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const handleStart = () => {
    if (!form.keyword.trim()) return
    setLoading(true)
    RunLinkedInScrapeService(
      { keyword: form.keyword, location: form.location, target_roles: form.target_roles, max_companies: form.max_companies, max_people: form.max_people },
      () => { setLoading(false); onStarted(form.keyword.trim()) },
      () => setLoading(false)
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">

        {/* Header — always visible */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Linkedin size={18} className="text-[#0077b5]" />
            <h3 className="text-sm font-black text-gray-900">LinkedIn AI Scraper</h3>
          </div>
          {!loading && <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100"><X size={16} /></button>}
        </div>

        {/* Body — switches between form and loading */}
        <AnimatePresence mode="wait">
          {loading ? (
            <ModalLoadingView key="loading" keyword={form.keyword} />
          ) : (
            <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="px-6 py-5 space-y-4">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-700">
                  Scrapes LinkedIn directly using your saved session + Gemini AI to extract and qualify leads. Runs in background — results appear in the companies list below.
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">Industry / Keyword *</label>
                  <input value={form.keyword} onChange={e => f('keyword', e.target.value)}
                    placeholder="e.g. logistics, manufacturing, pharma"
                    className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-gray-600 block mb-1">Location</label>
                    <input value={form.location} onChange={e => f('location', e.target.value)}
                      placeholder="India"
                      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-600 block mb-1">Max Companies</label>
                    <input type="number" value={form.max_companies} onChange={e => f('max_companies', Number(e.target.value))}
                      min={1} max={30}
                      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">Target Roles <span className="text-gray-400">(comma-separated)</span></label>
                  <input value={form.target_roles} onChange={e => f('target_roles', e.target.value)}
                    placeholder="Manager,Director,CEO,Operations"
                    className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600 block mb-1">Max People per Company</label>
                  <input type="number" value={form.max_people} onChange={e => f('max_people', Number(e.target.value))}
                    min={1} max={10}
                    className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white" />
                </div>
              </div>
              <div className="px-6 pb-5 flex gap-3">
                <button onClick={onClose} className="flex-1 h-10 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50">Cancel</button>
                <button onClick={handleStart} disabled={!form.keyword.trim()}
                  className="flex-1 h-10 rounded-xl flex items-center justify-center gap-2 text-white text-sm font-bold hover:opacity-90 disabled:opacity-50 transition-all"
                  style={{ background: '#0077b5' }}>
                  <Linkedin size={14} /> Start Scrape
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}

// Fake profile cards that fly across during scraping
const FAKE_PROFILES = [
  { name: 'Rajesh Kumar', title: 'Operations Manager', company: 'Tata Industries' },
  { name: 'Priya Sharma', title: 'Procurement Director', company: 'Reliance Ltd' },
  { name: 'Amit Verma', title: 'CEO', company: 'Infosys B2B' },
  { name: 'Sunita Patel', title: 'Plant Manager', company: 'L&T Automation' },
  { name: 'Vikram Singh', title: 'VP Operations', company: 'Mahindra Group' },
  { name: 'Neha Joshi', title: 'Supply Chain Head', company: 'ONGC Supply' },
]

function ProfileCard({ profile, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 80, scale: 0.9 }}
      animate={{ opacity: [0, 1, 1, 0], x: [80, 0, 0, -80], scale: [0.9, 1, 1, 0.9] }}
      transition={{ duration: 2.8, delay, repeat: Infinity, repeatDelay: FAKE_PROFILES.length * 0.9 - 2.8, ease: 'easeInOut' }}
      className="absolute bg-white rounded-xl shadow-lg border border-[#0077b5]/20 px-4 py-3 flex items-center gap-3 w-64"
    >
      <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
        style={{ background: '#0077b5' }}>
        {profile.name[0]}
      </div>
      <div className="min-w-0">
        <p className="text-xs font-bold text-gray-800 truncate">{profile.name}</p>
        <p className="text-[10px] text-gray-500 truncate">{profile.title}</p>
        <p className="text-[10px] text-[#0077b5] truncate">{profile.company}</p>
      </div>
      <Linkedin size={12} className="text-[#0077b5] flex-shrink-0 opacity-60" />
    </motion.div>
  )
}

// Full-screen scraping overlay
function ScrapingBanner({ keyword, elapsed, newCount, onDismiss }) {
  const dots = '.'.repeat((Math.floor(elapsed / 1.5) % 3) + 1)
  const mins = Math.floor(elapsed / 60)
  const secs = Math.floor(elapsed % 60)
  const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

  const steps = [
    'Launching browser session…',
    'Navigating to LinkedIn search…',
    'Scanning people profiles…',
    'Extracting contact details…',
    'Qualifying leads with AI…',
  ]
  const currentStep = Math.min(Math.floor(elapsed / 30), steps.length - 1)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(6px)' }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 24 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.9 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
        className="relative w-full max-w-md mx-4 rounded-3xl overflow-hidden shadow-2xl"
        style={{ background: 'linear-gradient(145deg, #003d6b 0%, #0077b5 60%, #00a0dc 100%)' }}
      >
        {/* Dismiss */}
        <button onClick={onDismiss}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-all z-10">
          <X size={14} />
        </button>

        <div className="px-8 pt-8 pb-6 flex flex-col items-center gap-6">

          {/* Big pulsing LinkedIn icon */}
          <div className="relative">
            <motion.div
              animate={{ scale: [1, 1.1, 1], boxShadow: ['0 0 0 0 rgba(255,255,255,0.2)', '0 0 0 18px rgba(255,255,255,0)', '0 0 0 0 rgba(255,255,255,0)'] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="w-20 h-20 rounded-2xl flex items-center justify-center bg-white/20 border-2 border-white/30"
            >
              <Linkedin size={36} className="text-white" />
            </motion.div>
            {/* Orbiting dot */}
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-0"
            >
              <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-amber-400 border-2 border-white shadow-md" />
            </motion.div>
          </div>

          {/* Title */}
          <div className="text-center">
            <p className="text-white font-black text-lg leading-tight">
              Scraping LinkedIn{dots}
            </p>
            <p className="text-white/70 text-sm mt-1">
              Searching for <span className="text-white font-bold">"{keyword}"</span>
            </p>
          </div>

          {/* Animated equalizer bars */}
          <div className="flex items-end gap-1.5 h-10">
            {[0.3, 0.6, 1, 0.5, 0.8, 0.4, 0.9, 0.6, 0.7, 0.35].map((h, i) => (
              <motion.div key={i}
                className="w-2 rounded-full bg-white/60"
                style={{ originY: 1 }}
                animate={{ scaleY: [h, 1, h] }}
                transition={{ duration: 0.6 + i * 0.05, delay: i * 0.08, repeat: Infinity, ease: 'easeInOut' }}
              />
            ))}
          </div>

          {/* Floating profile cards area */}
          <div className="relative w-full h-16 flex items-center justify-center overflow-hidden">
            {FAKE_PROFILES.map((profile, i) => (
              <ProfileCard key={i} profile={profile} delay={i * 0.9} />
            ))}
          </div>

          {/* Steps */}
          <div className="w-full space-y-2">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                  i < currentStep ? 'bg-emerald-400' :
                  i === currentStep ? 'bg-amber-400' : 'bg-white/20'
                }`}>
                  {i < currentStep ? (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3 5.5L6.5 2" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  ) : i === currentStep ? (
                    <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 0.8, repeat: Infinity }}
                      className="w-1.5 h-1.5 rounded-full bg-white" />
                  ) : null}
                </div>
                <p className={`text-xs transition-all ${
                  i < currentStep ? 'text-white/50 line-through' :
                  i === currentStep ? 'text-white font-semibold' : 'text-white/30'
                }`}>{step}</p>
              </div>
            ))}
          </div>

          {/* Stats row */}
          <div className="w-full flex items-center justify-between bg-white/10 rounded-2xl px-5 py-3">
            <div className="text-center">
              <p className="text-white/60 text-[10px] uppercase tracking-wide">Elapsed</p>
              <p className="text-white font-bold text-sm">{timeStr}</p>
            </div>
            <div className="w-px h-8 bg-white/20" />
            <div className="text-center">
              <p className="text-white/60 text-[10px] uppercase tracking-wide">Found</p>
              <p className="text-white font-bold text-sm">{newCount > 0 ? newCount : '—'}</p>
            </div>
            <div className="w-px h-8 bg-white/20" />
            <div className="text-center">
              <p className="text-white/60 text-[10px] uppercase tracking-wide">Status</p>
              <p className="text-emerald-300 font-bold text-sm">Live</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="w-full">
            <div className="h-1.5 rounded-full bg-white/20 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-white"
                animate={{ width: ['0%', '90%'] }}
                transition={{ duration: 180, ease: 'linear' }}
              />
            </div>
            <p className="text-white/40 text-[10px] text-center mt-2">Results appear automatically · dismiss anytime</p>
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function LeadDiscovery() {
  const [form, setForm] = useState({ industry: '', keywords: '', location: '', company_size: '', target_roles: '', max_results: 10 })
  const [searching, setSearching] = useState(false)
  const [showLinkedIn, setShowLinkedIn] = useState(false)
  const [companies, setCompanies] = useState([])
  const [contacts, setContacts] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ search: '', industry: '', interest_level: '' })
  const [selectedContacts, setSelectedContacts] = useState([])
  const [showModal, setShowModal] = useState(false)
  const [scoring, setScoring] = useState(false)
  const [lastSearch, setLastSearch] = useState(null)
  const [activeView, setActiveView] = useState('companies')

  // Dynamic filter options — populated from DB
  const [industryOptions, setIndustryOptions] = useState([])

  // Scraping state
  const [scraping, setScraping] = useState(null) // { keyword, startedAt, newCount }
  const [scrapingElapsed, setScrapingElapsed] = useState(0)
  const pollRef = useRef(null)
  const timerRef = useRef(null)
  const baseCountRef = useRef(0)

  // Load all unique industries from DB for the dropdown
  const refreshIndustryOptions = useCallback(() => {
    GetProspectCompaniesService({ page: 1, limit: 500 },
      d => {
        const items = d.items || []
        const unique = [...new Set(items.map(c => c.industry).filter(Boolean))].sort()
        setIndustryOptions(unique)
      },
      () => {}
    )
  }, [])

  useEffect(() => { refreshIndustryOptions() }, [refreshIndustryOptions])

  const loadCompanies = useCallback((resetPage = false) => {
    const p = resetPage ? 1 : page
    if (resetPage) setPage(1)
    const params = { page: p, limit: 20 }
    if (filters.search) params.search = filters.search
    if (filters.industry) params.industry = filters.industry
    if (filters.interest_level) params.interest_level = filters.interest_level
    GetProspectCompaniesService(params,
      d => {
        setCompanies(d.items || [])
        setTotal(d.total || 0)
        // Merge any new industries into the dropdown options
        const newIndustries = (d.items || []).map(c => c.industry).filter(Boolean)
        setIndustryOptions(prev => {
          const merged = [...new Set([...prev, ...newIndustries])].sort()
          return merged
        })
      },
      () => {}
    )
  }, [page, filters])

  const loadContacts = useCallback((resetPage = false) => {
    const p = resetPage ? 1 : page
    if (resetPage) setPage(1)
    const params = { page: p, limit: 20 }
    if (filters.search) params.search = filters.search
    GetProspectContactsService(params,
      d => { setContacts(d.items || []); setTotal(d.total || 0) },
      () => {}
    )
  }, [page, filters])

  useEffect(() => {
    if (activeView === 'companies') loadCompanies()
    else loadContacts()
  }, [activeView, loadCompanies, loadContacts])

  // Start scraping — save baseline count, begin polling
  const startScraping = (keyword) => {
    setShowLinkedIn(false)
    baseCountRef.current = total
    setScraping({ keyword, startedAt: Date.now(), newCount: 0 })
    setScrapingElapsed(0)
  }

  // Scraping ticker + auto-poll
  useEffect(() => {
    if (!scraping) return

    // Elapsed timer — tick every second
    timerRef.current = setInterval(() => {
      const elapsed = (Date.now() - scraping.startedAt) / 1000
      setScrapingElapsed(elapsed)

      // Auto-dismiss after 3 minutes
      if (elapsed >= 180) stopScraping()
    }, 1000)

    // Poll for new data every 15 seconds
    pollRef.current = setInterval(() => {
      GetProspectCompaniesService({ page: 1, limit: 20 },
        d => {
          const newTotal = d.total || 0
          const newCount = Math.max(0, newTotal - baseCountRef.current)
          setScraping(s => s ? { ...s, newCount } : null)

          if (newCount > 0) {
            // New leads arrived — refresh the list at page 1
            setPage(1)
            setCompanies(d.items || [])
            setTotal(newTotal)
            loadContacts(true)
          }
        },
        () => {}
      )
    }, 15000)

    return () => {
      clearInterval(timerRef.current)
      clearInterval(pollRef.current)
    }
  }, [scraping?.startedAt])

  const stopScraping = () => {
    clearInterval(timerRef.current)
    clearInterval(pollRef.current)
    // Final refresh at page 1 + rebuild industry dropdown
    loadCompanies(true)
    loadContacts(true)
    refreshIndustryOptions()
    setScraping(null)
  }

  const handleSearch = () => {
    setSearching(true)
    const payload = {
      industry: form.industry || undefined,
      keywords: form.keywords || undefined,
      location: form.location || undefined,
      company_size: form.company_size || undefined,
      target_roles: form.target_roles ? form.target_roles.split(',').map(r => r.trim()).filter(Boolean) : [],
      max_results: form.max_results,
    }
    RunDiscoverySearchService(payload,
      res => {
        setSearching(false)
        setLastSearch(res)
        loadCompanies(true)
        loadContacts(true)
      },
      () => setSearching(false)
    )
  }

  const handleScore = () => {
    setScoring(true)
    ScoreCompaniesService(null,
      () => { setScoring(false); loadCompanies() },
      () => setScoring(false)
    )
  }

  const toggleContact = (contact) => {
    setSelectedContacts(prev =>
      prev.find(c => c.id === contact.id) ? prev.filter(c => c.id !== contact.id) : [...prev, contact]
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-xl font-black text-gray-900">Lead Discovery</h1>
            <p className="text-xs text-gray-400 mt-0.5">Search companies and contacts by industry, keyword, or location</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setShowLinkedIn(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 transition-all shadow-md"
              style={{ background: '#0077b5' }}>
              <Linkedin size={14} /> LinkedIn Scrape
            </button>
            {selectedContacts.length > 0 && (
              <button onClick={() => setShowModal(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 transition-all">
                <Plus size={15} /> Add {selectedContacts.length} to Campaign
              </button>
            )}
            <button onClick={handleScore} disabled={scoring}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 text-sm font-semibold text-gray-600 hover:border-indigo-300 transition-all disabled:opacity-50">
              <Zap size={14} className={scoring ? 'animate-pulse text-amber-500' : 'text-amber-500'} />
              {scoring ? 'Scoring…' : 'AI Score All'}
            </button>
          </div>
        </div>

        {/* Search form */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <p className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2"><Search size={15} className="text-indigo-500" /> Discovery Search</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Industry</label>
              <input value={form.industry} onChange={e => setForm(p => ({...p, industry: e.target.value}))} placeholder="e.g. manufacturing, IT, logistics"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Keywords</label>
              <input value={form.keywords} onChange={e => setForm(p => ({...p, keywords: e.target.value}))} placeholder="e.g. Tata, automation, sensor"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Location</label>
              <input value={form.location} onChange={e => setForm(p => ({...p, location: e.target.value}))} placeholder="e.g. Mumbai, India"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Target Roles <span className="text-gray-400">(comma-separated)</span></label>
              <input value={form.target_roles} onChange={e => setForm(p => ({...p, target_roles: e.target.value}))} placeholder="e.g. Plant Manager, CTO, Automation Engineer"
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all" />
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Company Size</label>
              <select value={form.company_size} onChange={e => setForm(p => ({...p, company_size: e.target.value}))}
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all">
                <option value="">Any size</option>
                {SIZES.map(s => <option key={s} value={s}>{s} employees</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-gray-500 mb-1 block">Max Results</label>
              <select value={form.max_results} onChange={e => setForm(p => ({...p, max_results: Number(e.target.value)}))}
                className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400 bg-gray-50 focus:bg-white transition-all">
                {[5,10,15,20].map(n => <option key={n} value={n}>{n} companies</option>)}
              </select>
            </div>
          </div>
          <div className="flex justify-end mt-4">
            <button onClick={handleSearch} disabled={searching}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-indigo-200">
              {searching ? <><RefreshCw size={15} className="animate-spin" />Searching…</> : <><Search size={15} />Run Discovery</>}
            </button>
          </div>
          {lastSearch && (
            <div className="mt-3 p-3 bg-emerald-50 rounded-xl flex items-center gap-3 text-xs text-emerald-700">
              <CheckCircle size={14} />
              Found {lastSearch.companies_found} companies and {lastSearch.contacts_found} contacts for "{lastSearch.search_query}"
            </div>
          )}
        </div>

        {/* Results */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* Tabs + filters */}
          <div className="px-6 py-4 border-b border-gray-50 space-y-3">
            {/* Top row: tabs + live badge */}
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex bg-gray-100 rounded-xl overflow-hidden">
                {[['companies', 'Companies'], ['contacts', 'Contacts']].map(([k, l]) => (
                  <button key={k} onClick={() => { setActiveView(k); setPage(1) }}
                    className={`px-4 py-2 text-sm font-semibold transition-all ${activeView === k ? 'bg-indigo-600 text-white' : 'text-gray-500 hover:text-gray-700'}`}>
                    {l}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                {scraping && (
                  <div className="flex items-center gap-1.5 text-xs text-[#0077b5] font-semibold">
                    <Loader2 size={12} className="animate-spin" /> Live
                  </div>
                )}
                <span className="text-xs text-gray-400">{total} total</span>
              </div>
            </div>

            {/* Filter row */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* Search */}
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  value={filters.search}
                  onChange={e => setFilters(p => ({ ...p, search: e.target.value }))}
                  placeholder="Search name…"
                  className="pl-8 pr-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 w-36"
                />
              </div>

              {/* Dynamic industry dropdown — only for companies */}
              {activeView === 'companies' && (
                <div className="relative">
                  <Tag size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  <select
                    value={filters.industry}
                    onChange={e => setFilters(p => ({ ...p, industry: e.target.value }))}
                    className="pl-7 pr-7 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 bg-white appearance-none cursor-pointer"
                  >
                    <option value="">All Industries</option>
                    {industryOptions.map(ind => (
                      <option key={ind} value={ind}>{ind}</option>
                    ))}
                  </select>
                  <ChevronRight size={11} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none rotate-90" />
                </div>
              )}

              {/* Interest level — only for companies */}
              {activeView === 'companies' && (
                <select
                  value={filters.interest_level}
                  onChange={e => setFilters(p => ({ ...p, interest_level: e.target.value }))}
                  className="px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-400 bg-white"
                >
                  <option value="">All Levels</option>
                  <option value="hot">🔥 Hot</option>
                  <option value="warm">🟡 Warm</option>
                  <option value="cold">🔵 Cold</option>
                </select>
              )}

              {/* Clear filters button */}
              {(filters.search || filters.industry || filters.interest_level) && (
                <button
                  onClick={() => setFilters({ search: '', industry: '', interest_level: '' })}
                  className="flex items-center gap-1 px-2.5 py-2 text-xs text-gray-500 hover:text-red-500 border border-gray-200 rounded-lg hover:border-red-200 transition-all"
                >
                  <X size={11} /> Clear
                </button>
              )}
            </div>
          </div>

          {activeView === 'companies' ? (
            <div className="divide-y divide-gray-50">
              {companies.length === 0 ? (
                <div className="py-16 text-center text-gray-400">
                  <Building2 size={32} className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">{scraping ? 'Scraping in progress — results will appear here shortly…' : 'No companies yet — run a discovery search above'}</p>
                </div>
              ) : companies.map(company => (
                <div key={company.id} className="px-6 py-4 hover:bg-gray-50/50 transition-colors">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-100 to-indigo-50 flex items-center justify-center flex-shrink-0">
                      <Building2 size={18} className="text-indigo-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-gray-900">{company.name}</p>
                          <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                            {company.industry && <span className="flex items-center gap-1 text-xs text-gray-500"><Tag size={10} />{company.industry}</span>}
                            {company.location && <span className="flex items-center gap-1 text-xs text-gray-500"><MapPin size={10} />{company.location}</span>}
                            {company.company_size && <span className="flex items-center gap-1 text-xs text-gray-500"><Users size={10} />{company.company_size}</span>}
                            {company.website && (
                              <a href={company.website} target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700" onClick={e => e.stopPropagation()}>
                                <Globe size={10} />{new URL(company.website.startsWith('http') ? company.website : 'https://'+company.website).hostname}
                              </a>
                            )}
                          </div>
                          {company.description && <p className="text-xs text-gray-400 mt-1 line-clamp-1">{company.description}</p>}
                        </div>
                        <ScoreBadge score={company.ai_score} level={company.interest_level} />
                      </div>
                      {company.ai_score_reasoning && (
                        <p className="text-[10px] text-gray-400 mt-1 italic">{company.ai_score_reasoning}</p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {contacts.length === 0 ? (
                <div className="py-16 text-center text-gray-400">
                  <Users size={32} className="mx-auto mb-2 opacity-30" />
                  <p className="text-sm">{scraping ? 'Scraping in progress — contacts will appear here shortly…' : 'No contacts yet — run a discovery search with target roles'}</p>
                </div>
              ) : contacts.map(contact => {
                const isSelected = selectedContacts.find(c => c.id === contact.id)
                return (
                  <div key={contact.id} onClick={() => toggleContact(contact)}
                    className={`px-6 py-4 cursor-pointer transition-all ${isSelected ? 'bg-indigo-50/60' : 'hover:bg-gray-50/50'}`}>
                    <div className="flex items-center gap-4">
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-sm font-black text-white flex-shrink-0
                        ${isSelected ? 'bg-indigo-600' : 'bg-gradient-to-br from-slate-400 to-slate-500'}`}>
                        {isSelected ? <CheckCircle size={16} /> : (contact.name?.[0] || '?').toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-bold text-gray-900">{contact.name}</p>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {contact.email && <span className="text-xs text-gray-400">{contact.email}</span>}
                            {contact.linkedin_url && (
                              <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                                className="text-blue-500 hover:text-blue-700">
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 mt-0.5">
                          {contact.job_title && <span className="flex items-center gap-1 text-xs text-gray-500"><Briefcase size={10} />{contact.job_title}</span>}
                          {contact.company && <span className="flex items-center gap-1 text-xs text-indigo-500"><Building2 size={10} />{contact.company.name}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-50">
              <button disabled={page === 1} onClick={() => setPage(p => p-1)}
                className="text-xs font-bold text-gray-500 hover:text-indigo-600 disabled:opacity-30">← Prev</button>
              <span className="text-xs text-gray-400">{page} / {Math.ceil(total/20)}</span>
              <button disabled={page >= Math.ceil(total/20)} onClick={() => setPage(p => p+1)}
                className="text-xs font-bold text-gray-500 hover:text-indigo-600 disabled:opacity-30">Next →</button>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <AddToCampaignModal
          selectedContacts={selectedContacts}
          onClose={() => setShowModal(false)}
          onSuccess={count => { setShowModal(false); setSelectedContacts([]); alert(`Added ${count} contacts to campaign!`) }}
        />
      )}

      <AnimatePresence>
        {showLinkedIn && (
          <LinkedInScrapeModal
            onClose={() => setShowLinkedIn(false)}
            onStarted={startScraping}
          />
        )}
      </AnimatePresence>

      {/* Full-screen scraping overlay */}
      <AnimatePresence>
        {scraping && (
          <ScrapingBanner
            keyword={scraping.keyword}
            elapsed={scrapingElapsed}
            newCount={scraping.newCount}
            onDismiss={stopScraping}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

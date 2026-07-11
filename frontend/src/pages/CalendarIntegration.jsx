import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronLeft, ChevronRight, RefreshCw, ExternalLink,
  Video, Calendar, Clock, User, Zap, Brain, MousePointer, Shield, X,
  CheckCircle, AlertCircle, CalendarDays, Briefcase, Tag,
  Plus
} from 'lucide-react'
import {
  GetCalendarEventsService,
  GetAvailabilityService,
  UpdateAvailabilityDayService,
  GetSchedulingConfigService,
  UpdateSchedulingConfigService,
  ScheduleMeetingService,
  CancelEventService,
  RescheduleEventService,
} from '../services/ApiService'

// ─── Config ──────────────────────────────────────────────────────────────────

const TRIGGER_CONFIG = {
  deal_signal: {
    label: 'Deal Signal',
    bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500',
    border: 'border-emerald-200', icon: Zap,
  },
  manual: {
    label: 'Manual',
    bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500',
    border: 'border-blue-200', icon: MousePointer,
  },
  rag_insufficient: {
    label: 'AI Gap',
    bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500',
    border: 'border-amber-200', icon: Brain,
  },
}

const STATUS_CONFIG = {
  scheduled: { label: 'Scheduled', bg: 'bg-blue-100', text: 'text-blue-700', icon: Clock },
  completed: { label: 'Completed', bg: 'bg-gray-100', text: 'text-gray-600', icon: CheckCircle },
  cancelled: { label: 'Cancelled', bg: 'bg-red-100', text: 'text-red-600', icon: AlertCircle },
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December']

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildGrid(year, month) {
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const daysInPrev = new Date(year, month, 0).getDate()
  const days = []
  for (let i = firstDay - 1; i >= 0; i--)
    days.push({ day: daysInPrev - i, cur: false, date: new Date(year, month - 1, daysInPrev - i) })
  for (let d = 1; d <= daysInMonth; d++)
    days.push({ day: d, cur: true, date: new Date(year, month, d) })
  while (days.length < 42)
    days.push({ day: days.length - firstDay - daysInMonth + 1, cur: false, date: new Date(year, month + 1, days.length - firstDay - daysInMonth + 1) })
  return days
}

function dateKey(dt) {
  if (!dt) return ''
  const d = new Date(dt)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function fmtTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
}

function formatDealValue(description) {
  const match = description?.match(/Deal value: ₹([\d,]+)/)
  return match ? `₹${match[1]}` : null
}

// ─── Event Chip ─────────────────────────────────────────────────────────────

function EventChip({ event, onClick }) {
  const cfg = TRIGGER_CONFIG[event.trigger] || TRIGGER_CONFIG.manual
  const isCancelled = event.status === 'cancelled'
  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={(e) => { e.stopPropagation(); onClick(event) }}
      className={`w-full text-left px-1.5 py-0.5 rounded-md text-[10px] font-medium truncate transition-all flex items-center gap-1
        ${cfg.bg} ${cfg.text} ${isCancelled ? 'opacity-40 line-through' : ''}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      <span className="truncate">
        {fmtTime(event.start_time)} • {event.attendee_email?.split('@')[0]}
        {event.owner_email && <span className="opacity-60 ml-1">({event.owner_email.split('@')[0]})</span>}
      </span>
    </motion.button>
  )
}

// ─── Event Detail Panel ─────────────────────────────────────────────────────

function EventDetail({ event, onClose, onRefresh }) {
  const cfg = TRIGGER_CONFIG[event.trigger] || TRIGGER_CONFIG.manual
  const stCfg = STATUS_CONFIG[event.status] || STATUS_CONFIG.scheduled
  const Icon = cfg.icon
  const StatusIcon = stCfg.icon
  const dealValue = formatDealValue(event.description)

  return (
    <motion.div
      initial={{ opacity: 0, x: 20, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 20, scale: 0.96 }}
      transition={{ type: 'spring', damping: 25 }}
      className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden"
    >
      {/* Header */}
      <div className={`bg-gradient-to-r ${cfg.bg} p-4 border-b ${cfg.border}`}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-white/80 shadow-sm">
              <Icon size={16} className={cfg.text} />
            </div>
            <div>
              <p className={`text-sm font-bold ${cfg.text}`}>{cfg.label}</p>
              <div className="flex items-center gap-1 mt-0.5">
                <Calendar size={10} className="text-gray-400" />
                <p className="text-[10px] text-gray-500">{fmtDate(event.start_time)}</p>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-full hover:bg-white/60 text-gray-400">
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Status badge */}
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold ${stCfg.bg} ${stCfg.text} ring-1 ring-inset ${stCfg.bg.replace('bg-', 'ring-')}`}>
          <StatusIcon size={12} />
          {stCfg.label}
        </div>

        {/* Title */}
        <div>
          <h3 className="text-base font-bold text-gray-900">{event.title}</h3>
          {event.description && (
            <p className="text-xs text-gray-600 mt-1 whitespace-pre-wrap">{event.description}</p>
          )}
        </div>

        {/* Attendee & Time */}
        <div className="space-y-3 bg-gray-50/50 rounded-xl p-3">
          <div className="flex items-start gap-3">
            <User size={14} className="text-gray-400 mt-0.5" />
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wide">Attendee</p>
              <p className="text-sm font-medium text-gray-800">{event.attendee_email || '—'}</p>
            </div>
          </div>
          {event.owner_email && (
            <div className="flex items-start gap-3">
              <Shield size={14} className="text-violet-400 mt-0.5" />
              <div>
                <p className="text-[10px] text-gray-400 uppercase tracking-wide">Scheduled by</p>
                <p className="text-sm font-medium text-violet-700">{event.owner_email}</p>
              </div>
            </div>
          )}
          <div className="flex items-start gap-3">
            <Clock size={14} className="text-gray-400 mt-0.5" />
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wide">Time</p>
              <p className="text-sm font-medium text-gray-800">
                {fmtTime(event.start_time)} – {fmtTime(event.end_time)}
              </p>
            </div>
          </div>
        </div>

        {/* Lead & Deal IDs */}
        {(event.lead_id || event.deal_id) && (
          <div className="flex flex-wrap gap-2 text-xs">
            {event.lead_id && (
              <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-50 text-indigo-700">
                <Briefcase size={10} />
                Lead: {event.lead_id.slice(-8)}
              </div>
            )}
            {event.deal_id && (
              <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-purple-50 text-purple-700">
                <Tag size={10} />
                Deal: {event.deal_id.slice(-8)}
              </div>
            )}
            {dealValue && (
              <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-50 text-emerald-700">
                <span className="font-bold">{dealValue}</span>
              </div>
            )}
          </div>
        )}

        {/* Links */}
        <div className="space-y-2">
          {event.meet_link && (
            <a href={event.meet_link} target="_blank" rel="noreferrer"
              className="flex items-center gap-2 p-2.5 rounded-xl bg-blue-50 text-blue-700 hover:bg-blue-100 transition-all text-sm font-medium">
              <Video size={14} />
              Join Google Meet
              <ExternalLink size={12} className="ml-auto" />
            </a>
          )}
          {event.calendar_link && (
            <a href={event.calendar_link} target="_blank" rel="noreferrer"
              className="flex items-center gap-2 p-2.5 rounded-xl bg-gray-50 text-gray-700 hover:bg-gray-100 transition-all text-sm font-medium">
              <Calendar size={14} />
              Open in Google Calendar
              <ExternalLink size={12} className="ml-auto" />
            </a>
          )}
        </div>

        {/* Invite status */}
        {event.invite_email_sent && (
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 p-2.5 rounded-xl">
            <CheckCircle size={14} />
            Invite email sent
          </div>
        )}

        {/* Actions — only for non-cancelled events */}
        {event.status !== 'cancelled' && (
          <div className="flex gap-2 pt-1 border-t border-gray-100">
            <button
              onClick={() => {
                if (!confirm('Reschedule to next available slot?')) return
                RescheduleEventService(event.id, {},
                  () => { onRefresh(); onClose() },
                  (_, e) => alert('Reschedule failed: ' + e)
                )
              }}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border border-indigo-200 text-indigo-600 text-xs font-semibold hover:bg-indigo-50 transition-all"
            >
              <RefreshCw size={12} />
              Reschedule
            </button>
            <button
              onClick={() => {
                if (!confirm(`Cancel "${event.title}"? This will notify the attendee.`)) return
                CancelEventService(event.id,
                  () => { onRefresh(); onClose() },
                  (_, e) => alert('Cancel failed: ' + e)
                )
              }}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border border-red-200 text-red-600 text-xs font-semibold hover:bg-red-50 transition-all"
            >
              <X size={12} />
              Cancel Meeting
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ─── Main Calendar Component ────────────────────────────────────────────────

const DAYS_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const BUFFER_OPTIONS = [0, 10, 15, 20, 30, 45, 60]

function AvailabilityPanel() {
  const [availability, setAvailability] = useState([])
  const [config, setConfig] = useState({ buffer_minutes: 15, slot_duration_minutes: 30, max_meetings_per_day: 8 })
  const [saving, setSaving] = useState(null) // day_of_week being saved, or 'config'
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    Promise.all([
      new Promise(res => GetAvailabilityService(res, () => res([]))),
      new Promise(res => GetSchedulingConfigService(res, () => res(null))),
    ]).then(([avail, cfg]) => {
      setAvailability(avail || [])
      if (cfg) setConfig(cfg)
      setLoaded(true)
    })
  }, [])

  const updateDay = (dow, field, value) => {
    setAvailability(prev => prev.map(d =>
      d.day_of_week === dow ? { ...d, [field]: value } : d
    ))
  }

  const saveDay = (day) => {
    setSaving(day.day_of_week)
    UpdateAvailabilityDayService(day.day_of_week, {
      is_available: day.is_available,
      start_hour: day.start_hour,
      start_minute: day.start_minute,
      end_hour: day.end_hour,
      end_minute: day.end_minute,
    },
      () => setSaving(null),
      (_s, err) => { setSaving(null); alert('Save failed: ' + err) }
    )
  }

  const saveConfig = () => {
    setSaving('config')
    UpdateSchedulingConfigService(config,
      () => setSaving(null),
      (_s, err) => { setSaving(null); alert('Save failed: ' + err) }
    )
  }

  if (!loaded) return <div className="flex justify-center py-10 text-gray-400 text-sm">Loading availability...</div>

  return (
    <div className="space-y-5">
      {/* Buffer & slot config */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Meeting Settings</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">
              Buffer between meetings
            </label>
            <select value={config.buffer_minutes}
              onChange={e => setConfig(c => ({ ...c, buffer_minutes: Number(e.target.value) }))}
              className="w-full px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 focus:outline-none focus:border-blue-400">
              {BUFFER_OPTIONS.map(m => (
                <option key={m} value={m}>{m === 0 ? 'No buffer' : `${m} min`}</option>
              ))}
            </select>
            <p className="text-[10px] text-gray-400 mt-1">Prevents back-to-back meetings</p>
          </div>
          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">
              Default slot duration
            </label>
            <select value={config.slot_duration_minutes}
              onChange={e => setConfig(c => ({ ...c, slot_duration_minutes: Number(e.target.value) }))}
              className="w-full px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 focus:outline-none focus:border-blue-400">
              {[15, 20, 30, 45, 60, 90].map(m => (
                <option key={m} value={m}>{m} min</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">
              Max meetings per day
            </label>
            <select value={config.max_meetings_per_day}
              onChange={e => setConfig(c => ({ ...c, max_meetings_per_day: Number(e.target.value) }))}
              className="w-full px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 focus:outline-none focus:border-blue-400">
              {[2,3,4,5,6,7,8,10,12].map(n => (
                <option key={n} value={n}>{n} meetings</option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button onClick={saveConfig} disabled={saving === 'config'}
            className="px-5 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all disabled:opacity-60">
            {saving === 'config' ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>

      {/* Per-day availability */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Weekly Availability</h3>
        <div className="space-y-3">
          {availability.map(day => (
            <div key={day.day_of_week}
              className={`flex items-center gap-4 p-3 rounded-xl transition-all ${
                day.is_available ? 'bg-gray-50' : 'bg-gray-50/40 opacity-60'
              }`}>
              {/* Toggle */}
              <button onClick={() => updateDay(day.day_of_week, 'is_available', !day.is_available)}
                className={`w-9 h-5 rounded-full transition-colors flex-shrink-0 relative ${
                  day.is_available ? 'bg-blue-600' : 'bg-gray-300'
                }`}>
                <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${
                  day.is_available ? 'left-4' : 'left-0.5'
                }`} />
              </button>

              {/* Day name */}
              <span className="text-xs font-semibold text-gray-700 w-24 flex-shrink-0">
                {DAYS_LONG[day.day_of_week]}
              </span>

              {/* Time range */}
              {day.is_available ? (
                <div className="flex items-center gap-2 flex-1">
                  <select value={day.start_hour}
                    onChange={e => updateDay(day.day_of_week, 'start_hour', Number(e.target.value))}
                    className="px-2 py-1 text-xs rounded-lg bg-white border border-gray-200 focus:outline-none focus:border-blue-400">
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>
                    ))}
                  </select>
                  <span className="text-xs text-gray-400">to</span>
                  <select value={day.end_hour}
                    onChange={e => updateDay(day.day_of_week, 'end_hour', Number(e.target.value))}
                    className="px-2 py-1 text-xs rounded-lg bg-white border border-gray-200 focus:outline-none focus:border-blue-400">
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>
                    ))}
                  </select>
                  <span className="text-[10px] text-gray-400 ml-1">
                    {day.end_hour - day.start_hour}h window
                  </span>
                </div>
              ) : (
                <span className="text-xs text-gray-400 flex-1">Not available</span>
              )}

              {/* Save */}
              <button onClick={() => saveDay(day)} disabled={saving === day.day_of_week}
                className="flex-shrink-0 px-3 py-1 rounded-lg bg-blue-50 text-blue-600 text-xs font-semibold hover:bg-blue-100 transition-all disabled:opacity-60">
                {saving === day.day_of_week ? '...' : 'Save'}
              </button>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-gray-400 mt-3">
          The scheduler will only book meetings within these hours, with the configured buffer between slots.
        </p>
      </div>
    </div>
  )
}

export default function CalendarIntegration() {
  const today = new Date()
  const [activeTab, setActiveTab] = useState('calendar')
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDay, setSelectedDay] = useState(null)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [newMeetingOpen, setNewMeetingOpen] = useState(false)
  const [meetingForm, setMeetingForm] = useState({
    attendee_email: '', title: '', description: '',
    start_time: '', duration_minutes: 30,
  })
  const [schedulingMeeting, setSchedulingMeeting] = useState(false)
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  const fetchEvents = () => {
    setLoading(true)
    GetCalendarEventsService({ limit: 100 },
      (data) => { setEvents(data?.items || []); setLoading(false) },
      () => setLoading(false)
    )
  }

  useEffect(() => { fetchEvents() }, [])

  const eventsByDate = useMemo(() => {
    const map = {}
    events.forEach(ev => {
      const k = dateKey(ev.start_time)
      if (!map[k]) map[k] = []
      map[k].push(ev)
    })
    // sort events within each day by start time
    Object.keys(map).forEach(k => {
      map[k].sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
    })
    return map
  }, [events])

  const grid = useMemo(() => buildGrid(year, month), [year, month])

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }
  const goToday = () => {
    setYear(today.getFullYear())
    setMonth(today.getMonth())
    setSelectedDay(today)
  }

  const todayKey = dateKey(today)
  const selectedKey = selectedDay ? dateKey(selectedDay) : null
  const dayEvents = selectedKey ? (eventsByDate[selectedKey] || []) : []

  // Stats
  const totalEvents = events.length
  const scheduled = events.filter(e => e.status === 'scheduled').length
  const completed = events.filter(e => e.status === 'completed').length
  const dealSignals = events.filter(e => e.trigger === 'deal_signal').length
  const manual = events.filter(e => e.trigger === 'manual').length

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-gray-100 p-6">
      <div className="max-w-[1600px] mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Sales Calendar
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {totalEvents} events · {dealSignals} deal signals · {manual} manual meetings
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* New Meeting button */}
            <button
              onClick={() => setNewMeetingOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition-all shadow-sm"
            >
              <Plus size={14} />
              New Meeting
            </button>
            {/* Tab switcher */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-white border border-gray-200 shadow-sm">
              <button onClick={() => setActiveTab('calendar')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'calendar' ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}>
                Calendar
              </button>
              <button onClick={() => setActiveTab('availability')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === 'availability' ? 'bg-indigo-600 text-white shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}>
                Availability
              </button>
            </div>
            <button
              onClick={fetchEvents}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin text-indigo-500' : ''} />
              <span className="text-sm font-medium text-gray-600">Refresh</span>
            </button>
          </div>
        </div>

        {/* Availability settings tab */}
        {activeTab === 'availability' && <AvailabilityPanel />}

        {/* Calendar tab content */}
        {activeTab === 'calendar' && <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Events', value: totalEvents, icon: CalendarDays, color: 'text-indigo-600', bg: 'bg-indigo-50' },
            { label: 'Scheduled', value: scheduled, icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50' },
            { label: 'Completed', value: completed, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' },
            { label: 'Deal Signals', value: dealSignals, icon: Zap, color: 'text-amber-600', bg: 'bg-amber-50' },
          ].map((stat, idx) => (
            <motion.div
              key={idx}
              whileHover={{ y: -2 }}
              className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between">
                <div className={`p-2 rounded-xl ${stat.bg}`}>
                  <stat.icon size={18} className={stat.color} />
                </div>
                <span className="text-2xl font-bold text-gray-800">{stat.value}</span>
              </div>
              <p className="text-xs text-gray-500 mt-2">{stat.label}</p>
            </motion.div>
          ))}
        </div>

        {/* Calendar + Sidebar */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Calendar Card */}
          <div className="flex-1 bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-gray-100 bg-gray-50/30">
              <div className="flex items-center gap-2">
                <button
                  onClick={prevMonth}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-all"
                >
                  <ChevronLeft size={18} />
                </button>
                <h2 className="text-base font-bold text-gray-800 min-w-[140px] text-center">
                  {MONTHS[month]} {year}
                </h2>
                <button
                  onClick={nextMonth}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-all"
                >
                  <ChevronRight size={18} />
                </button>
                <button
                  onClick={goToday}
                  className="ml-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-all"
                >
                  Today
                </button>
              </div>

              {/* Legend */}
              <div className="hidden md:flex items-center gap-3">
                {Object.entries(TRIGGER_CONFIG).map(([k, cfg]) => (
                  <div key={k} className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                    <span className="text-[10px] text-gray-500">{cfg.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Weekday Headers */}
            <div className="grid grid-cols-7 border-b border-gray-100 bg-gray-50/50">
              {WEEKDAYS.map(d => (
                <div key={d} className="py-3 text-center text-[11px] font-semibold text-gray-500 uppercase tracking-wide">
                  {d}
                </div>
              ))}
            </div>

            {/* Calendar Grid */}
            {loading ? (
              <div className="flex justify-center items-center py-32">
                <RefreshCw size={28} className="animate-spin text-gray-300" />
              </div>
            ) : (
              <div className="grid grid-cols-7">
                {grid.map((cell, i) => {
                  const k = dateKey(cell.date)
                  const cellEvents = eventsByDate[k] || []
                  const isToday = k === todayKey
                  const isSelected = k === selectedKey
                  const isCurrentMonth = cell.cur

                  return (
                    <motion.div
                      key={i}
                      whileHover={{ backgroundColor: '#fafafa' }}
                      onClick={() => setSelectedDay(isSelected ? null : cell.date)}
                      className={`min-h-[100px] p-2 border-b border-r border-gray-100 cursor-pointer transition-all
                        ${isSelected ? 'bg-indigo-50/60 ring-1 ring-inset ring-indigo-200' : ''}
                        ${i % 7 === 6 ? 'border-r-0' : ''}
                        ${i >= 35 ? 'border-b-0' : ''}
                      `}
                    >
                      {/* Day Number */}
                      <div className="flex justify-end mb-1.5">
                        <span className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-semibold
                          ${isToday ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-sm' : ''}
                          ${isSelected && !isToday ? 'ring-2 ring-indigo-400 text-indigo-700' : ''}
                          ${isCurrentMonth ? 'text-gray-700' : 'text-gray-300'}
                        `}>
                          {cell.day}
                        </span>
                      </div>

                      {/* Events */}
                      <div className="space-y-1">
                        {cellEvents.slice(0, 2).map((ev, idx) => (
                          <EventChip
                            key={ev.id || idx}
                            event={ev}
                            onClick={(ev) => { setSelectedDay(cell.date); setSelectedEvent(ev) }}
                          />
                        ))}
                        {cellEvents.length > 2 && (
                          <p className="text-[9px] text-gray-400 pl-1">+{cellEvents.length - 2} more</p>
                        )}
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Right Panel */}
          <div className="w-full lg:w-80 flex-shrink-0">
            <AnimatePresence mode="wait">
              {selectedEvent ? (
                <EventDetail key="detail" event={selectedEvent} onClose={() => setSelectedEvent(null)} onRefresh={fetchEvents} />
              ) : selectedDay ? (
                <motion.div
                  key="day"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden"
                >
                  <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-gradient-to-r from-gray-50 to-white">
                    <div>
                      <p className="text-sm font-bold text-gray-800">{fmtDate(selectedDay)}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{dayEvents.length} event{dayEvents.length !== 1 ? 's' : ''}</p>
                    </div>
                    <button onClick={() => setSelectedDay(null)} className="p-1.5 rounded-full hover:bg-gray-100 text-gray-400">
                      <X size={14} />
                    </button>
                  </div>
                  <div className="p-4 space-y-2 max-h-[500px] overflow-y-auto">
                    {dayEvents.length === 0 ? (
                      <div className="text-center py-8">
                        <Calendar size={32} className="mx-auto text-gray-200 mb-2" />
                        <p className="text-xs text-gray-400">No events this day</p>
                      </div>
                    ) : (
                      dayEvents.map((ev, idx) => {
                        const cfg = TRIGGER_CONFIG[ev.trigger] || TRIGGER_CONFIG.manual
                        const Icon = cfg.icon
                        return (
                          <motion.button
                            key={ev.id || idx}
                            whileHover={{ scale: 1.01 }}
                            onClick={() => setSelectedEvent(ev)}
                            className={`w-full text-left p-3 rounded-xl border transition-all hover:shadow-sm ${cfg.bg} ${cfg.border}`}
                          >
                            <div className="flex items-center gap-2 mb-2">
                              <Icon size={12} className={cfg.text} />
                              <span className={`text-[10px] font-bold ${cfg.text}`}>{cfg.label}</span>
                              <span className="ml-auto text-[9px] px-2 py-0.5 rounded-full bg-white/70">
                                {fmtTime(ev.start_time)}
                              </span>
                            </div>
                            <p className="text-xs font-medium text-gray-700 truncate">{ev.title}</p>
                            <p className="text-[10px] text-gray-400 mt-0.5">{ev.attendee_email}</p>
                          </motion.button>
                        )
                      })
                    )}
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="hint"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6 text-center"
                >
                  <div className="w-14 h-14 rounded-full bg-indigo-50 flex items-center justify-center mx-auto mb-3">
                    <CalendarDays size={24} className="text-indigo-400" />
                  </div>
                  <p className="text-sm font-medium text-gray-700">Select a day</p>
                  <p className="text-xs text-gray-400 mt-1">Click any date to see scheduled meetings</p>

                  <div className="mt-6 space-y-2">
                    {Object.entries(TRIGGER_CONFIG).map(([k, cfg]) => {
                      const count = events.filter(e => e.trigger === k).length
                      return (
                        <div key={k} className={`flex items-center justify-between px-3 py-2 rounded-xl ${cfg.bg}`}>
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                            <span className={`text-xs font-medium ${cfg.text}`}>{cfg.label}</span>
                          </div>
                          <span className={`text-xs font-bold ${cfg.text}`}>{count}</span>
                        </div>
                      )
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
        </div>} {/* end calendar tab */}

      </div>

      {/* ── New Meeting Modal ── */}
      {newMeetingOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-gray-900">Schedule New Meeting</h2>
                <p className="text-xs text-gray-400 mt-0.5">A Google Meet link will be created and invite sent</p>
              </div>
              <button onClick={() => setNewMeetingOpen(false)}>
                <X size={16} className="text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-600">Attendee Email *</label>
                <input
                  type="email"
                  value={meetingForm.attendee_email}
                  onChange={e => setMeetingForm(f => ({ ...f, attendee_email: e.target.value }))}
                  placeholder="customer@example.com"
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400"
                />
                {meetingForm.attendee_email && !EMAIL_RE.test(meetingForm.attendee_email.trim()) && (
                  <p className="text-[10px] text-red-500 mt-1">Enter a valid email address</p>
                )}
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Meeting Title *</label>
                <input
                  value={meetingForm.title}
                  onChange={e => setMeetingForm(f => ({ ...f, title: e.target.value }))}
                  placeholder="e.g. Product Demo — Industrial Data Logger"
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Start Date & Time *</label>
                <input
                  type="datetime-local"
                  value={meetingForm.start_time}
                  onChange={e => setMeetingForm(f => ({ ...f, start_time: e.target.value }))}
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Duration</label>
                <select
                  value={meetingForm.duration_minutes}
                  onChange={e => setMeetingForm(f => ({ ...f, duration_minutes: Number(e.target.value) }))}
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-400"
                >
                  {[15, 20, 30, 45, 60, 90].map(m => (
                    <option key={m} value={m}>{m} minutes</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600">Description (optional)</label>
                <textarea
                  value={meetingForm.description}
                  onChange={e => setMeetingForm(f => ({ ...f, description: e.target.value }))}
                  rows={3}
                  placeholder="Agenda, notes, products to discuss..."
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 rounded-xl resize-none focus:outline-none focus:border-indigo-400"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setNewMeetingOpen(false)}
                className="flex-1 py-2.5 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                disabled={
                  schedulingMeeting || !meetingForm.attendee_email || !meetingForm.title ||
                  !meetingForm.start_time || !EMAIL_RE.test(meetingForm.attendee_email.trim())
                }
                onClick={() => {
                  setSchedulingMeeting(true)
                  ScheduleMeetingService({
                    attendee_email: meetingForm.attendee_email.trim(),
                    title: meetingForm.title,
                    description: meetingForm.description,
                    start_time: new Date(meetingForm.start_time).toISOString(),
                    duration_minutes: meetingForm.duration_minutes,
                  },
                    () => {
                      setSchedulingMeeting(false)
                      setNewMeetingOpen(false)
                      setMeetingForm({ attendee_email: '', title: '', description: '', start_time: '', duration_minutes: 30 })
                      fetchEvents()
                    },
                    (_s, err) => { setSchedulingMeeting(false); alert('Failed to schedule: ' + err) }
                  )
                }}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-all"
              >
                <Video size={14} />
                {schedulingMeeting ? 'Scheduling…' : 'Create Meeting'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  )
}
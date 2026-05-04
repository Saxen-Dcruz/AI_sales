import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Brain,
  Briefcase,
  Calendar,
  CalendarDays,
  CheckCircle,
  ChevronLeft, ChevronRight,
  Clock,
  ExternalLink,
  MousePointer,
  RefreshCw,
  Tag,
  User,
  Video,
  X,
  Zap
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { GetCalendarEventsService } from '../services/ApiService'

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
      <span className="truncate">{fmtTime(event.start_time)} • {event.attendee_email?.split('@')[0]}</span>
    </motion.button>
  )
}

// ─── Event Detail Panel ─────────────────────────────────────────────────────

function EventDetail({ event, onClose }) {
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
      </div>
    </motion.div>
  )
}

// ─── Main Calendar Component ────────────────────────────────────────────────

export default function CalendarIntegration() {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth())
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDay, setSelectedDay] = useState(null)
  const [selectedEvent, setSelectedEvent] = useState(null)

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
          <button
            onClick={fetchEvents}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin text-indigo-500' : ''} />
            <span className="text-sm font-medium text-gray-600">Refresh</span>
          </button>
        </div>

        {/* Stats Cards */}
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
                <EventDetail key="detail" event={selectedEvent} onClose={() => setSelectedEvent(null)} />
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
      </div>
    </div>
  )
}
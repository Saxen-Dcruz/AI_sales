import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronLeft, ChevronRight, RefreshCw, ExternalLink,
  Video, Calendar, Clock, User, Zap, Brain, MousePointer, X
} from 'lucide-react'
import { GetCalendarEventsService } from '../services/ApiService'

// ─── Config ──────────────────────────────────────────────────────────────────

const TRIGGER_CONFIG = {
  deal_signal: {
    label: 'Deal Signal',
    bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500',
    border: 'border-emerald-300', chip: 'bg-emerald-500',
    icon: Zap, priority: 1,
  },
  manual: {
    label: 'Manual',
    bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-500',
    border: 'border-blue-300', chip: 'bg-blue-500',
    icon: MousePointer, priority: 2,
  },
  rag_insufficient: {
    label: 'AI Gap',
    bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500',
    border: 'border-amber-300', chip: 'bg-amber-500',
    icon: Brain, priority: 3,
  },
}

const STATUS_CONFIG = {
  scheduled: { label: 'Scheduled', bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-200' },
  completed: { label: 'Completed', bg: 'bg-gray-50', text: 'text-gray-500', ring: 'ring-gray-200' },
  cancelled: { label: 'Cancelled', bg: 'bg-red-50', text: 'text-red-500', ring: 'ring-red-200' },
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

function fmt(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
}

// ─── Event chip ──────────────────────────────────────────────────────────────

function EventChip({ event, onClick }) {
  const cfg = TRIGGER_CONFIG[event.trigger] || TRIGGER_CONFIG.manual
  const isCancelled = event.status === 'cancelled'
  return (
    <button onClick={e => { e.stopPropagation(); onClick(event) }}
      className={`w-full text-left px-1.5 py-0.5 rounded-md text-[10px] font-medium truncate transition-all hover:brightness-95 flex items-center gap-1
        ${cfg.bg} ${cfg.text} ${isCancelled ? 'opacity-40 line-through' : ''}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
      <span className="truncate">{fmt(event.start_time)} {event.attendee_email?.split('@')[0]}</span>
    </button>
  )
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function EventDetail({ event, onClose }) {
  const cfg = TRIGGER_CONFIG[event.trigger] || TRIGGER_CONFIG.manual
  const stCfg = STATUS_CONFIG[event.status] || STATUS_CONFIG.scheduled
  const Icon = cfg.icon

  return (
    <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 16 }}
      className="bg-white border border-gray-200 rounded-2xl shadow-lg overflow-hidden">
      {/* Header */}
      <div className={`p-4 ${cfg.bg} border-b ${cfg.border}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-lg bg-white/60`}>
              <Icon size={14} className={cfg.text} />
            </div>
            <div>
              <p className={`text-xs font-bold ${cfg.text}`}>{cfg.label}</p>
              <p className="text-[10px] text-gray-500">{fmtDate(event.start_time)}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/60 text-gray-400 transition-all">
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {/* Status */}
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold ring-1 ${stCfg.bg} ${stCfg.text} ${stCfg.ring}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${event.status === 'scheduled' ? 'bg-blue-500' : event.status === 'completed' ? 'bg-gray-400' : 'bg-red-500'}`} />
          {stCfg.label}
        </div>

        {/* Details */}
        <div className="space-y-2.5">
          <div className="flex items-start gap-2.5">
            <User size={13} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[10px] text-gray-400">Attendee</p>
              <p className="text-xs font-medium text-gray-800">{event.attendee_email || '—'}</p>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <Clock size={13} className="text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-[10px] text-gray-400">Time</p>
              <p className="text-xs font-medium text-gray-800">
                {fmt(event.start_time)} – {fmt(event.end_time)}
              </p>
            </div>
          </div>
          {event.meet_link && (
            <div className="flex items-start gap-2.5">
              <Video size={13} className="text-gray-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-[10px] text-gray-400">Google Meet</p>
                <a href={event.meet_link} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors">
                  Join Meeting <ExternalLink size={10} />
                </a>
              </div>
            </div>
          )}
          {event.calendar_link && (
            <div className="flex items-start gap-2.5">
              <Calendar size={13} className="text-gray-400 mt-0.5 flex-shrink-0" />
              <a href={event.calendar_link} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-800 transition-colors">
                Open in Google Calendar <ExternalLink size={10} />
              </a>
            </div>
          )}
        </div>

        {/* Invite sent badge */}
        {event.invite_email_sent && (
          <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 px-2.5 py-1.5 rounded-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Invite email sent
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

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
    GetCalendarEventsService({ limit: 200 },
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
    return map
  }, [events])

  const grid = useMemo(() => buildGrid(year, month), [year, month])

  const prevMonth = () => { if (month === 0) { setMonth(11); setYear(y => y - 1) } else setMonth(m => m - 1) }
  const nextMonth = () => { if (month === 11) { setMonth(0); setYear(y => y + 1) } else setMonth(m => m + 1) }
  const goToday = () => { setYear(today.getFullYear()); setMonth(today.getMonth()) }

  const todayKey = dateKey(today)
  const selectedKey = selectedDay ? dateKey(selectedDay) : null
  const dayEvents = selectedKey ? (eventsByDate[selectedKey] || []) : []

  // Stats
  const scheduled = events.filter(e => e.status === 'scheduled').length
  const completed = events.filter(e => e.status === 'completed').length
  const dealSignals = events.filter(e => e.trigger === 'deal_signal').length
  const aiGaps = events.filter(e => e.trigger === 'rag_insufficient').length

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Events', value: events.length, color: 'text-primary-400' },
          { label: 'Scheduled', value: scheduled, color: 'text-blue-500' },
          { label: 'Completed', value: completed, color: 'text-accent-green' },
          { label: 'Deal Signals', value: dealSignals, color: 'text-emerald-500' },
        ].map((s, i) => (
          <div key={i} className="glass-card p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Calendar + detail panel */}
      <div className="flex gap-4 items-start">

        {/* Calendar */}
        <div className="flex-1 glass-card overflow-hidden">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-3">
              <button onClick={prevMonth}
                className="p-1.5 rounded-xl hover:bg-gray-100 text-gray-500 transition-all">
                <ChevronLeft size={16} />
              </button>
              <h2 className="text-sm font-bold text-gray-900 w-40 text-center">
                {MONTHS[month]} {year}
              </h2>
              <button onClick={nextMonth}
                className="p-1.5 rounded-xl hover:bg-gray-100 text-gray-500 transition-all">
                <ChevronRight size={16} />
              </button>
              <button onClick={goToday}
                className="ml-1 px-3 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 transition-all">
                Today
              </button>
            </div>

            <div className="flex items-center gap-4">
              {/* Legend */}
              <div className="hidden md:flex items-center gap-3">
                {Object.entries(TRIGGER_CONFIG).map(([k, c]) => (
                  <div key={k} className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${c.dot}`} />
                    <span className="text-[10px] text-gray-500">{c.label}</span>
                  </div>
                ))}
              </div>
              <button onClick={fetchEvents}
                className="p-1.5 rounded-xl hover:bg-gray-100 text-gray-400 transition-all">
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 border-b border-gray-100">
            {WEEKDAYS.map(d => (
              <div key={d} className="py-2 text-center text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                {d}
              </div>
            ))}
          </div>

          {/* Grid */}
          {loading ? (
            <div className="flex justify-center py-20 text-gray-400 text-sm">Loading events...</div>
          ) : (
            <div className="grid grid-cols-7">
              {grid.map((cell, i) => {
                const k = dateKey(cell.date)
                const cellEvents = eventsByDate[k] || []
                const isToday = k === todayKey
                const isSelected = k === selectedKey
                const isCurrentMonth = cell.cur

                return (
                  <div key={i}
                    onClick={() => setSelectedDay(isSelected ? null : cell.date)}
                    className={`min-h-[90px] p-1.5 border-b border-r border-gray-100 cursor-pointer transition-colors
                      ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'}
                      ${i % 7 === 6 ? 'border-r-0' : ''}
                      ${i >= 35 ? 'border-b-0' : ''}`}>

                    {/* Day number */}
                    <div className="flex justify-end mb-1">
                      <span className={`w-6 h-6 flex items-center justify-center rounded-full text-[11px] font-semibold
                        ${isToday ? 'bg-blue-600 text-white' : ''}
                        ${isSelected && !isToday ? 'ring-2 ring-blue-400' : ''}
                        ${isCurrentMonth ? (isToday ? '' : 'text-gray-800') : 'text-gray-300'}`}>
                        {cell.day}
                      </span>
                    </div>

                    {/* Event chips — show max 2, +N more */}
                    <div className="space-y-0.5">
                      {cellEvents.slice(0, 2).map((ev, ei) => (
                        <EventChip key={ei} event={ev}
                          onClick={(ev) => { setSelectedDay(cell.date); setSelectedEvent(ev) }} />
                      ))}
                      {cellEvents.length > 2 && (
                        <p className="text-[9px] text-gray-400 pl-1">+{cellEvents.length - 2} more</p>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right panel — day events or event detail */}
        <div className="w-72 flex-shrink-0 space-y-3">
          <AnimatePresence mode="wait">
            {selectedEvent ? (
              <EventDetail key="detail" event={selectedEvent} onClose={() => setSelectedEvent(null)} />
            ) : selectedDay ? (
              <motion.div key="day" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}
                className="glass-card overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-bold text-gray-900">{fmtDate(selectedDay)}</p>
                    <p className="text-[10px] text-gray-400">{dayEvents.length} event{dayEvents.length !== 1 ? 's' : ''}</p>
                  </div>
                  <button onClick={() => setSelectedDay(null)} className="p-1 rounded-lg hover:bg-gray-100 text-gray-400">
                    <X size={13} />
                  </button>
                </div>
                <div className="p-3 space-y-2 max-h-[400px] overflow-y-auto">
                  {dayEvents.length === 0 ? (
                    <p className="text-xs text-gray-400 text-center py-4">No events this day</p>
                  ) : dayEvents.map((ev, i) => {
                    const cfg = TRIGGER_CONFIG[ev.trigger] || TRIGGER_CONFIG.manual
                    const Icon = cfg.icon
                    return (
                      <button key={i} onClick={() => setSelectedEvent(ev)}
                        className={`w-full text-left p-3 rounded-xl border transition-all hover:shadow-sm ${cfg.bg} ${cfg.border} border`}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <Icon size={12} className={cfg.text} />
                          <span className={`text-[10px] font-bold ${cfg.text}`}>{cfg.label}</span>
                          <span className={`ml-auto text-[9px] px-1.5 py-0.5 rounded-full ${STATUS_CONFIG[ev.status]?.bg} ${STATUS_CONFIG[ev.status]?.text}`}>
                            {ev.status}
                          </span>
                        </div>
                        <p className="text-xs font-medium text-gray-700 truncate">{ev.attendee_email}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{fmt(ev.start_time)} – {fmt(ev.end_time)}</p>
                      </button>
                    )
                  })}
                </div>
              </motion.div>
            ) : (
              <motion.div key="hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="glass-card p-6 text-center">
                <Calendar size={28} className="mx-auto text-gray-300 mb-3" />
                <p className="text-xs text-gray-400">Click any day to see events</p>
                <div className="mt-4 space-y-1.5">
                  {Object.entries(TRIGGER_CONFIG).map(([k, c]) => {
                    const count = events.filter(e => e.trigger === k).length
                    return (
                      <div key={k} className={`flex items-center justify-between px-3 py-1.5 rounded-lg ${c.bg}`}>
                        <div className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${c.dot}`} />
                          <span className={`text-[10px] font-medium ${c.text}`}>{c.label}</span>
                        </div>
                        <span className={`text-[10px] font-bold ${c.text}`}>{count}</span>
                      </div>
                    )
                  })}
                </div>
                {aiGaps > 0 && (
                  <div className="mt-3 p-2.5 rounded-lg bg-amber-50 border border-amber-200">
                    <p className="text-[10px] text-amber-700 font-medium">{aiGaps} AI Gap meeting{aiGaps > 1 ? 's' : ''} scheduled — knowledge gaps triggered calls</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </motion.div>
  )
}

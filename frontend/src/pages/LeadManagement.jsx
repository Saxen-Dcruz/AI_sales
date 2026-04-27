import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Search, Download, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { GetLeadsService } from '../services/ApiService'

const statusColors = {
  Qualified: 'badge-green', 'In Progress': 'badge-blue', Negotiating: 'badge-purple',
  'Demo Scheduled': 'badge-cyan', 'Proposal Sent': 'badge-orange', Contacted: 'badge-blue',
  New: 'badge-purple', Lost: 'badge-red', Uncontacted: 'badge-purple', Converted: 'badge-green',
}

const PAGE_SIZE = 6

function mapLead(l) {
  // Map backend LeadOut shape to the frontend table shape
  const source = l.inbound_first_contact ? 'Inbound' : l.linkedin_url ? 'LinkedIn' : 'Other'
  return {
    id:      l.id,
    name:    l.name,
    phone:   l.phone    || '—',
    company: l.company_name || '—',
    source,
    interest: l.classification || l.interest_level || '—',
    score:   l.engagement_score || 0,
    status:  l.status,
    summary: l.classification_reason || l.global_ai_summary || '—',
  }
}

function exportCSV(leads) {
  const headers = ['Name', 'Phone', 'Company', 'Source', 'Classification', 'Score', 'Status', 'Summary']
  const rows = leads.map(l => [l.name, l.phone, l.company, l.source, l.interest, l.score, l.status, `"${l.summary}"`])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = 'leads.csv'; a.click()
}

export default function LeadManagement() {
  const [leads, setLeads]       = useState([])
  const [total, setTotal]       = useState(0)
  const [loading, setLoading]   = useState(true)
  const [search, setSearch]     = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [page, setPage]         = useState(1)

  const fetchLeads = useCallback(() => {
    setLoading(true)
    const params = { page, limit: PAGE_SIZE }
    if (search)                  params.search = search
    if (statusFilter !== 'All')  params.status = statusFilter

    GetLeadsService(
      params,
      (data) => {
        setLeads((data.items || []).map(mapLead))
        setTotal(data.total || 0)
        setLoading(false)
      },
      () => setLoading(false)
    )
  }, [page, search, statusFilter])

  useEffect(() => { fetchLeads() }, [fetchLeads])

  // Reset page when filters change
  useEffect(() => { setPage(1) }, [search, statusFilter])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const start = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const end   = Math.min(page * PAGE_SIZE, total)

  const avgScore = leads.length ? Math.round(leads.reduce((a, l) => a + l.score, 0) / leads.length) : 0
  const qualified = leads.filter(l => l.status === 'Qualified' || l.interest === 'HIGH').length

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Leads',  value: total,       color: 'text-primary-400' },
          { label: 'HIGH Priority',value: qualified,   color: 'text-accent-green' },
          { label: 'On This Page', value: leads.length,color: 'text-accent-cyan' },
          { label: 'Avg Score',    value: avgScore,    color: 'text-accent-orange' },
        ].map((s, i) => (
          <div key={i} className="glass-card p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Table card */}
      <div className="glass-card p-5">
        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 mb-5">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search leads or company..."
              className="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 transition-all shadow-sm"
            />
          </div>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
            {['All', 'Uncontacted', 'Contacted', 'In Progress', 'Qualified', 'Negotiating', 'Demo Scheduled', 'Proposal Sent', 'Converted', 'Lost'].map(s =>
              <option key={s} value={s} className="bg-white">{s}</option>
            )}
          </select>
          <button onClick={() => exportCSV(leads)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 text-sm hover:bg-blue-100 transition-all font-medium">
            <Download size={14} /> Export CSV
          </button>
          <button onClick={fetchLeads}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-600 text-sm hover:bg-gray-100 transition-all ${loading ? 'opacity-50' : ''}`}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[900px]">
            <thead>
              <tr className="border-b border-gray-200">
                {['Lead Name', 'Phone', 'Company', 'Source', 'Classification', 'Score', 'Status', 'AI Summary'].map(h => (
                  <th key={h} className="text-left py-2.5 px-3 text-gray-500 font-medium uppercase tracking-wider text-[10px]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="py-3 px-3"><div className="h-3 rounded bg-gray-100 w-3/4" /></td>
                    ))}
                  </tr>
                ))
              ) : leads.length === 0 ? (
                <tr><td colSpan={8} className="py-8 text-center text-sm text-gray-400">No leads found</td></tr>
              ) : (
                leads.map((lead, i) => (
                  <motion.tr key={lead.id} className="table-row"
                    initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}>
                    <td className="py-3 px-3 font-semibold text-gray-900">{lead.name}</td>
                    <td className="py-3 px-3 text-gray-500 font-mono">{lead.phone}</td>
                    <td className="py-3 px-3 text-gray-600">{lead.company}</td>
                    <td className="py-3 px-3 font-semibold text-primary-400">{lead.source}</td>
                    <td className="py-3 px-3">
                      <span className={`badge ${lead.interest === 'HIGH' ? 'badge-green' : lead.interest === 'MEDIUM' ? 'badge-blue' : lead.interest === 'LOW' ? 'badge-red' : 'badge-purple'}`}>
                        {lead.interest}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-gray-900">{lead.score}</span>
                        <div className="w-12 h-1 rounded-full bg-gray-100">
                          <div className="h-full rounded-full"
                            style={{ width: `${lead.score}%`, background: lead.score >= 70 ? '#10b981' : lead.score >= 40 ? '#f59e0b' : '#ef4444' }} />
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`badge ${statusColors[lead.status] || 'badge-blue'}`}>{lead.status}</span>
                    </td>
                    <td className="py-3 px-3 text-gray-500 max-w-xs truncate">{lead.summary}</td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">Showing {start}–{end} of {total} leads</p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1 || loading}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(p => (
              <button key={p} onClick={() => setPage(p)}
                className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${p === page ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'}`}>
                {p}
              </button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages || loading}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

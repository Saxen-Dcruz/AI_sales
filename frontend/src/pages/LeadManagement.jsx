import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Search, Download, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { GetAllLeadsService, GetLeadClassificationSummaryService } from '../services/ApiService'

const classificationColors = {
  HIGH: 'badge-green',
  MEDIUM: 'badge-orange',
  LOW: 'badge-red',
  UNCLASSIFIED: 'badge-blue',
}

const statusColors = {
  active: 'badge-green',
  inactive: 'badge-red',
}

const PAGE_SIZE = 10

function exportCSV(leads) {
  const headers = ['Name', 'Email', 'Phone', 'Company', 'Status', 'Score', 'Classification', 'Next Action']
  const rows = leads.map(l => [
    l.name, l.email, l.phone || '', l.company_name || '',
    l.status, l.engagement_score || 0, l.classification,
    `"${(l.next_best_action || '').replace(/"/g, "'")}"`
  ])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'leads.csv'
  a.click()
}

export default function LeadManagement() {
  const [leads, setLeads] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [classificationFilter, setClassificationFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [page, setPage] = useState(1)

  const fetchLeads = useCallback(() => {
    setLoading(true)
    const params = {
      page,
      limit: PAGE_SIZE,
    }
    if (search) params.search = search
    if (classificationFilter !== 'All') params.classification = classificationFilter
    if (statusFilter !== 'All') params.status = statusFilter

    GetAllLeadsService(params, (data) => {
      setLeads(data.items || [])
      setTotal(data.total || 0)
      setLoading(false)
    }, (_status, err) => {
      console.error('Leads fetch failed:', err)
      setLoading(false)
    })
  }, [page, search, classificationFilter, statusFilter])

  useEffect(() => {
    GetLeadClassificationSummaryService((data) => setSummary(data), () => {})
  }, [])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads])

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [search, classificationFilter, statusFilter])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const summaryCards = [
    { label: 'Total Leads', value: summary?.total ?? total, color: 'text-primary-400' },
    { label: 'HIGH', value: summary?.tiers?.HIGH?.count ?? '—', color: 'text-accent-green' },
    { label: 'MEDIUM', value: summary?.tiers?.MEDIUM?.count ?? '—', color: 'text-accent-orange' },
    { label: 'LOW', value: summary?.tiers?.LOW?.count ?? '—', color: 'text-accent-red' },
  ]

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((s, i) => (
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
              placeholder="Search by name or email..."
              className="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 transition-all shadow-sm"
            />
          </div>
          <select value={classificationFilter} onChange={e => setClassificationFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
            {['All', 'HIGH', 'MEDIUM', 'LOW', 'UNCLASSIFIED'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
            {['All', 'active', 'inactive'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={fetchLeads}
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-600 text-sm hover:bg-gray-100 transition-all">
            <RefreshCw size={14} />
          </button>
          <button onClick={() => exportCSV(leads)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 text-sm hover:bg-blue-100 transition-all font-medium">
            <Download size={14} />
            Export CSV
          </button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-16 text-gray-400 text-sm">Loading leads...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[900px]">
              <thead>
                <tr className="border-b border-gray-200">
                  {['Name', 'Email', 'Phone', 'Company', 'Score', 'Classification', 'Status', 'Next Action'].map(h => (
                    <th key={h} className="text-left py-2.5 px-3 text-gray-500 font-medium uppercase tracking-wider text-[10px]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {leads.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-gray-400 text-sm">No leads found.</td>
                  </tr>
                ) : leads.map((lead, i) => (
                  <motion.tr key={lead.id} className="table-row"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}>
                    <td className="py-3 px-3 font-semibold text-gray-900">{lead.name}</td>
                    <td className="py-3 px-3 text-gray-500">{lead.email}</td>
                    <td className="py-3 px-3 text-gray-500 font-mono">{lead.phone || '—'}</td>
                    <td className="py-3 px-3 text-gray-600">{lead.company_name || '—'}</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-gray-900">{lead.engagement_score ?? 0}</span>
                        <div className="w-12 h-1 rounded-full bg-gray-100">
                          <div className="h-full rounded-full"
                            style={{
                              width: `${lead.engagement_score ?? 0}%`,
                              background: (lead.engagement_score ?? 0) >= 70 ? '#10b981' : (lead.engagement_score ?? 0) >= 40 ? '#f59e0b' : '#ef4444'
                            }} />
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`badge ${classificationColors[lead.classification] || 'badge-blue'}`}>
                        {lead.classification || 'UNCLASSIFIED'}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span className={`badge ${statusColors[lead.status] || 'badge-blue'}`}>{lead.status}</span>
                    </td>
                    <td className="py-3 px-3 text-gray-500 max-w-xs truncate">{lead.next_best_action || '—'}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            Showing {total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total} leads
          </p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map(p => (
              <button key={p} onClick={() => setPage(p)}
                className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${p === page ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'}`}>
                {p}
              </button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

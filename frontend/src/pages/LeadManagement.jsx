import { useState } from 'react'
import { motion } from 'framer-motion'
import { Search, Filter, Download, ChevronLeft, ChevronRight } from 'lucide-react'

const allLeads = [
  { id: 1, name: 'Sarah Mitchell', phone: '+1 555-0101', company: 'TechCorp', source: 'LinkedIn', interest: 'Enterprise Plan', score: 96, status: 'Qualified', summary: 'High intent, requested demo, budget confirmed.' },
  { id: 2, name: 'James Liu', phone: '+1 555-0102', company: 'DataSys', source: 'Inbound', interest: 'Growth Plan', score: 92, status: 'In Progress', summary: 'Called twice, very interested in automation features.' },
  { id: 3, name: 'Maria Gonzalez', phone: '+1 555-0103', company: 'CloudBase', source: 'LinkedIn', interest: 'Enterprise Plan', score: 88, status: 'Negotiating', summary: 'Evaluating 3 vendors, strongest preference for NexusAI.' },
  { id: 4, name: 'Tom Baker', phone: '+1 555-0104', company: 'AI Ventures', source: 'Sheet', interest: 'Starter Plan', score: 85, status: 'Demo Scheduled', summary: 'First contact via sheet import, interested in trial.' },
  { id: 5, name: 'Priya Patel', phone: '+1 555-0105', company: 'FinTech One', source: 'Inbound', interest: 'Growth Plan', score: 83, status: 'Proposal Sent', summary: 'Decision maker confirmed, proposal under review.' },
  { id: 6, name: 'Chris Evans', phone: '+1 555-0106', company: 'BuildFast', source: 'LinkedIn', interest: 'Enterprise Plan', score: 79, status: 'Contacted', summary: 'Initial contact made, awaiting callback.' },
  { id: 7, name: 'Anna Lee', phone: '+1 555-0107', company: 'MediaTech', source: 'Sheet', interest: 'Starter Plan', score: 74, status: 'New', summary: 'Freshly imported, not yet contacted.' },
  { id: 8, name: 'Robert Kim', phone: '+1 555-0108', company: 'HealthAI', source: 'Inbound', interest: 'Growth Plan', score: 70, status: 'Contacted', summary: 'Left voicemail. Needs healthcare compliance info.' },
  { id: 9, name: 'Emily Chen', phone: '+1 555-0109', company: 'StartupX', source: 'LinkedIn', interest: 'Starter Plan', score: 66, status: 'New', summary: 'Scraped from LinkedIn, tech-savvy profile.' },
  { id: 10, name: 'David Park', phone: '+1 555-0110', company: 'OutreachPro', source: 'Sheet', interest: 'Growth Plan', score: 61, status: 'In Progress', summary: 'Budget not confirmed, exploring options.' },
  { id: 11, name: 'Lisa Wang', phone: '+1 555-0111', company: 'ScaleUp', source: 'LinkedIn', interest: 'Enterprise Plan', score: 58, status: 'Lost', summary: 'Went with competitor. Price objection.' },
  { id: 12, name: 'Mark Taylor', phone: '+1 555-0112', company: 'GlobalTech', source: 'Inbound', interest: 'Starter Plan', score: 52, status: 'New', summary: 'Inbound inquiry last week.' },
]

const statusColors = {
  Qualified: 'badge-green',
  'In Progress': 'badge-blue',
  Negotiating: 'badge-purple',
  'Demo Scheduled': 'badge-cyan',
  'Proposal Sent': 'badge-orange',
  Contacted: 'badge-blue',
  New: 'badge-purple',
  Lost: 'badge-red',
}

const sourceColors = {
  LinkedIn: 'text-[#0077b5]',
  Inbound: 'text-primary-400',
  Sheet: 'text-accent-green',
}

const PAGE_SIZE = 6

function exportCSV(leads) {
  const headers = ['Name', 'Phone', 'Company', 'Source', 'Interest', 'Score', 'Status', 'Summary']
  const rows = leads.map(l => [l.name, l.phone, l.company, l.source, l.interest, l.score, l.status, `"${l.summary}"`])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'leads.csv'
  a.click()
}

export default function LeadManagement() {
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [page, setPage] = useState(1)

  const filtered = allLeads.filter(l => {
    const matchSearch = l.name.toLowerCase().includes(search.toLowerCase()) ||
      l.company.toLowerCase().includes(search.toLowerCase())
    const matchSource = sourceFilter === 'All' || l.source === sourceFilter
    const matchStatus = statusFilter === 'All' || l.status === statusFilter
    return matchSearch && matchSource && matchStatus
  })

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Leads', value: allLeads.length, color: 'text-primary-400' },
          { label: 'Qualified', value: allLeads.filter(l => l.status === 'Qualified').length, color: 'text-accent-green' },
          { label: 'In Progress', value: allLeads.filter(l => l.status === 'In Progress').length, color: 'text-accent-cyan' },
          { label: 'Avg Score', value: Math.round(allLeads.reduce((a, l) => a + l.score, 0) / allLeads.length), color: 'text-accent-orange' },
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
              onChange={e => { setSearch(e.target.value); setPage(1) }}
              placeholder="Search leads or company..."
              className="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 transition-all shadow-sm"
            />
          </div>
          <select value={sourceFilter} onChange={e => { setSourceFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
            {['All', 'LinkedIn', 'Inbound', 'Sheet'].map(s => <option key={s} value={s} className="bg-white">{s}</option>)}
          </select>
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
            className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
            {['All', 'New', 'Contacted', 'In Progress', 'Qualified', 'Negotiating', 'Demo Scheduled', 'Proposal Sent', 'Lost'].map(s =>
              <option key={s} value={s} className="bg-white">{s}</option>
            )}
          </select>
          <button onClick={() => exportCSV(filtered)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-600 text-sm hover:bg-blue-100 transition-all font-medium">
            <Download size={14} />
            Export CSV
          </button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[900px]">
            <thead>
              <tr className="border-b border-gray-200">
                {['Lead Name', 'Phone', 'Company', 'Source', 'Interest', 'Score', 'Status', 'AI Summary'].map(h => (
                  <th key={h} className="text-left py-2.5 px-3 text-gray-500 font-medium uppercase tracking-wider text-[10px]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginated.map((lead, i) => (
                <motion.tr key={lead.id} className="table-row"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}>
                  <td className="py-3 px-3 font-semibold text-gray-900">{lead.name}</td>
                  <td className="py-3 px-3 text-gray-500 font-mono">{lead.phone}</td>
                  <td className="py-3 px-3 text-gray-600">{lead.company}</td>
                  <td className={`py-3 px-3 font-semibold ${sourceColors[lead.source]}`}>{lead.source}</td>
                  <td className="py-3 px-3 text-gray-500">{lead.interest}</td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-gray-900">{lead.score}</span>
                      <div className="w-12 h-1 rounded-full bg-gray-100">
                        <div className="h-full rounded-full"
                          style={{ width: `${lead.score}%`, background: lead.score >= 80 ? '#10b981' : lead.score >= 60 ? '#f59e0b' : '#ef4444' }} />
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`badge ${statusColors[lead.status] || 'badge-blue'}`}>{lead.status}</span>
                  </td>
                  <td className="py-3 px-3 text-gray-500 max-w-xs truncate">{lead.summary}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">Showing {filtered.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} leads</p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronLeft size={14} />
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
              <button key={p} onClick={() => setPage(p)}
                className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${p === page ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'}`}>
                {p}
              </button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

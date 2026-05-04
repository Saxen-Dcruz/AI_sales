import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw, Search, ChevronDown, ChevronRight, CheckCircle,
  AlertTriangle, Package, Database, ExternalLink, Tag
} from 'lucide-react'
import { GetAllEmbeddingsService } from '../services/ApiService'

const CHUNK_COLORS = {
  description:        'bg-blue-50 text-blue-700 border-blue-200',
  features:           'bg-emerald-50 text-emerald-700 border-emerald-200',
  specification:      'bg-purple-50 text-purple-700 border-purple-200',
  specifications:     'bg-purple-50 text-purple-700 border-purple-200',
  package_contains:   'bg-amber-50 text-amber-700 border-amber-200',
  package_includes:   'bg-amber-50 text-amber-700 border-amber-200',
  frequently_bought_together: 'bg-pink-50 text-pink-700 border-pink-200',
  product_knowledge:  'bg-indigo-50 text-indigo-700 border-indigo-200',
}

function chunkColor(type) {
  return CHUNK_COLORS[type] || 'bg-gray-50 text-gray-600 border-gray-200'
}

function CoverageBar({ pct }) {
  const color = pct >= 70 ? '#10b981' : pct >= 30 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <motion.div className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }} />
      </div>
      <span className="text-[10px] font-bold w-8 text-right" style={{ color }}>{pct}%</span>
    </div>
  )
}

function ProductRow({ product }) {
  const [open, setOpen] = useState(false)
  const [expandedChunk, setExpandedChunk] = useState(null)
  const hasChunks = product.total_chunks > 0

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${
      hasChunks ? 'border-gray-200' : 'border-red-200 bg-red-50/30'
    }`}>
      {/* Header row */}
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-4 px-4 py-3 hover:bg-gray-50/60 transition-all text-left">
        <div className="flex-shrink-0">
          {hasChunks
            ? <CheckCircle size={16} className="text-emerald-500" />
            : <AlertTriangle size={16} className="text-red-400" />}
        </div>

        {/* Name + order code */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-gray-900 truncate max-w-xs">{product.name}</span>
            {product.order_code && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                {product.order_code}
              </span>
            )}
            {product.category && (
              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-600 font-medium">
                {product.category}
              </span>
            )}
          </div>
        </div>

        {/* Pricing */}
        <div className="flex items-center gap-4 flex-shrink-0 text-xs">
          <div className="text-right hidden sm:block">
            <p className="text-[9px] text-gray-400">Single</p>
            <p className="font-semibold text-gray-800">
              {product.single_price ? `₹${Number(product.single_price).toLocaleString()}` : '—'}
            </p>
          </div>
          <div className="text-right hidden md:block">
            <p className="text-[9px] text-gray-400">Bulk</p>
            <p className="font-semibold text-gray-600">
              {product.bulk_price ? `₹${Number(product.bulk_price).toLocaleString()}` : '—'}
            </p>
          </div>
        </div>

        {/* Coverage + chunk count */}
        <div className="w-32 flex-shrink-0 hidden lg:block">
          <CoverageBar pct={product.coverage_score} />
        </div>
        <div className="flex-shrink-0 text-center w-16">
          <span className={`text-xs font-bold ${hasChunks ? 'text-emerald-600' : 'text-red-500'}`}>
            {product.total_chunks}
          </span>
          <p className="text-[9px] text-gray-400">chunks</p>
        </div>

        {/* Chunk type badges */}
        <div className="flex-shrink-0 flex gap-1 flex-wrap max-w-48 hidden xl:flex">
          {product.chunk_types.map(t => (
            <span key={t} className={`text-[8px] font-medium px-1.5 py-0.5 rounded border ${chunkColor(t)}`}>
              {t.replace(/_/g, ' ')}
            </span>
          ))}
        </div>

        <div className="flex-shrink-0 text-gray-400">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </button>

      {/* Expanded chunks */}
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-gray-100">

            {/* Product meta */}
            <div className="px-4 py-3 bg-gray-50/50 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Single Price</p>
                <p className="font-semibold text-gray-800">
                  {product.single_price ? `₹${Number(product.single_price).toLocaleString()}` : '—'}
                </p>
              </div>
              <div>
                <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Bulk Price</p>
                <p className="font-semibold text-gray-700">
                  {product.bulk_price ? `₹${Number(product.bulk_price).toLocaleString()}` : '—'}
                </p>
              </div>
              <div>
                <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Brand</p>
                <p className="font-semibold text-gray-700">{product.brand || '—'}</p>
              </div>
              <div>
                <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Coverage</p>
                <p className="font-semibold text-gray-700">{product.coverage_score}%</p>
              </div>
              {product.product_link && (
                <div className="col-span-2">
                  <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Product Link</p>
                  <a href={product.product_link} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline text-[10px]">
                    {product.product_link} <ExternalLink size={9} />
                  </a>
                </div>
              )}
              {product.datasheet_link && (
                <div className="col-span-2">
                  <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">Datasheet</p>
                  <a href={product.datasheet_link} target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-1 text-blue-600 hover:underline text-[10px]">
                    {product.datasheet_link} <ExternalLink size={9} />
                  </a>
                </div>
              )}
            </div>

            {/* Chunks */}
            {product.chunks.length === 0 ? (
              <div className="px-4 py-5 text-center">
                <AlertTriangle size={18} className="mx-auto text-red-400 mb-1.5" />
                <p className="text-xs text-red-500 font-medium">No embeddings stored for this product.</p>
                <p className="text-[10px] text-gray-400 mt-0.5">
                  Re-ingest via the data ingestion script or add knowledge base entries.
                </p>
              </div>
            ) : (
              <div className="p-3 space-y-2">
                {product.chunks.map((chunk) => (
                  <div key={chunk.chunk_id}>
                    <button onClick={() => setExpandedChunk(expandedChunk === chunk.chunk_id ? null : chunk.chunk_id)}
                      className="w-full flex items-center gap-2 text-left hover:bg-gray-50 rounded-lg px-2 py-1.5 transition-all group">
                      <span className={`text-[9px] font-semibold px-2 py-0.5 rounded border flex-shrink-0 ${chunkColor(chunk.chunk_type)}`}>
                        {chunk.chunk_type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-[10px] text-gray-500 truncate flex-1">
                        {chunk.doc_preview || chunk.document?.slice(0, 120)}
                      </span>
                      {expandedChunk === chunk.chunk_id
                        ? <ChevronDown size={11} className="text-gray-400 flex-shrink-0" />
                        : <ChevronRight size={11} className="text-gray-400 flex-shrink-0 opacity-0 group-hover:opacity-100" />}
                    </button>
                    <AnimatePresence>
                      {expandedChunk === chunk.chunk_id && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                          <pre className="text-[10px] text-gray-700 bg-gray-50 border border-gray-100 rounded-lg p-3 mx-2 mt-1 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto font-mono">
                            {chunk.document || chunk.doc_preview}
                          </pre>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function EmbeddingsPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all') // all | missing | has_chunks

  const fetchData = () => {
    setLoading(true)
    GetAllEmbeddingsService(
      (d) => { setData(d); setLoading(false) },
      (_s, err) => { console.error(err); setLoading(false) }
    )
  }

  useEffect(() => { fetchData() }, [])

  const items = data?.items || []
  const filtered = items.filter(p => {
    const matchSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.order_code || '').toLowerCase().includes(search.toLowerCase())
    const matchFilter =
      filter === 'all' ||
      (filter === 'missing' && p.total_chunks === 0) ||
      (filter === 'has_chunks' && p.total_chunks > 0)
    return matchSearch && matchFilter
  })

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Products', value: data?.total_products ?? '—', color: 'text-primary-400', icon: Package },
          { label: 'Total Chunks', value: data?.total_embeddings ?? '—', color: 'text-blue-500', icon: Database },
          { label: 'Not Embedded', value: data?.not_embedded?.length ?? '—', color: 'text-accent-red', icon: AlertTriangle },
          { label: 'Avg per Product',
            value: data?.total_products ? Math.round(data.total_embeddings / data.total_products) : '—',
            color: 'text-accent-green', icon: Tag },
        ].map((s, i) => (
          <div key={i} className="glass-card p-4 flex items-center gap-3">
            <div className={`p-2 rounded-xl bg-gray-100`}>
              <s.icon size={16} className={s.color} />
            </div>
            <div>
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Not-embedded warning */}
      {data?.not_embedded?.length > 0 && (
        <div className="glass-card p-4 border border-red-200 bg-red-50/40">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-red-700">
                {data.not_embedded.length} product{data.not_embedded.length > 1 ? 's' : ''} have no embeddings
              </p>
              <p className="text-[10px] text-red-500 mt-0.5">
                {data.not_embedded.join(' · ')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="glass-card p-4 flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by product name or order code..."
            className="w-full pl-8 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-400 transition-all" />
        </div>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-400">
          <option value="all">All products</option>
          <option value="has_chunks">Has embeddings</option>
          <option value="missing">Missing embeddings</option>
        </select>
        <button onClick={fetchData}
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100 transition-all">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
        <p className="text-xs text-gray-400 self-center flex-shrink-0">{filtered.length} products</p>
      </div>

      {/* Product list */}
      {loading ? (
        <div className="glass-card p-12 flex justify-center text-gray-400 text-sm">
          Loading embeddings...
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-12 text-center text-gray-400 text-sm">No products match.</div>
      ) : (
        <div className="space-y-2">
          {filtered.map(product => (
            <ProductRow key={product.product_id} product={product} />
          ))}
        </div>
      )}
    </motion.div>
  )
}

import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle
} from '@mui/material'
import { AnimatePresence, motion } from 'framer-motion'
import {
  BookOpen,
  ChevronLeft, ChevronRight,
  Edit2,
  ExternalLink,
  LayoutGrid, List,
  Package,
  Plus,
  Power, PowerOff,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { DeleteProductService, ShowAllProductService, ToggleActiveInactiveService } from '../services/ApiService'

function CoverageBar({ score }) {
  if (score === null || score === undefined) {
    return (
      <div>
        <div className="flex justify-between mb-1">
          <span className="text-[10px] text-gray-400">Knowledge Coverage</span>
          <span className="text-[10px] font-bold text-gray-400">No data</span>
        </div>
        <div className="h-1 rounded-full bg-gray-100" />
      </div>
    )
  }
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444'
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[10px] text-gray-400">Knowledge Coverage</span>
        <span className="text-[10px] font-bold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1 rounded-full bg-gray-100 overflow-hidden">
        <motion.div className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

function ProductCard({ product, onEdit, onKb, onToggle, onDelete, onView }) {
  const isActive = product.status === 'Active'
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-card p-5 flex flex-col gap-4 group hover:shadow-md transition-shadow"
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
            <Package size={18} className="text-blue-500" />
          </div>
          <div className="min-w-0">
            <button onClick={() => onView(product)}
              className="text-sm font-semibold text-gray-900 truncate max-w-[160px] block hover:text-blue-600 transition-colors text-left">
              {product.name}
            </button>
            <div className="flex items-center gap-1.5 mt-0.5">
              {product['Order Code'] && (
                <span className="text-[10px] font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
                  {product['Order Code']}
                </span>
              )}
              {product.Brand && (
                <span className="text-[10px] text-gray-400">{product.Brand}</span>
              )}
            </div>
          </div>
        </div>
        <span className={`flex-shrink-0 inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-lg ${isActive ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-400'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'}`} />
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* Category badges */}
      <div className="flex items-center gap-2 flex-wrap">
        {product.category && (
          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">
            <Tag size={9} />
            {product.category}
          </span>
        )}
        {product['Sub-category'] && (
          <span className="text-[10px] text-gray-400 px-2 py-0.5 rounded-full bg-gray-50">
            {product['Sub-category']}
          </span>
        )}
      </div>

      {/* Pricing */}
      <div className="flex items-center gap-4">
        <div>
          <p className="text-[10px] text-gray-400">Single</p>
          <p className="text-sm font-bold text-gray-900">
            {product.price || product.singlePrice ? `₹${Number(product.price || product.singlePrice).toLocaleString()}` : '—'}
          </p>
        </div>
        {(product.bulk_price > 0) && (
          <>
            <div className="w-px h-6 bg-gray-100" />
            <div>
              <p className="text-[10px] text-gray-400">Bulk</p>
              <p className="text-sm font-semibold text-gray-600">₹{Number(product.bulk_price).toLocaleString()}</p>
            </div>
          </>
        )}
      </div>

      {/* Coverage */}
      <CoverageBar score={product.coverage_score} />

      {/* Links */}
      {(product['Product Link'] || product['Data Sheet link']) && (
        <div className="flex items-center gap-2">
          {product['Product Link'] && (
            <a href={product['Product Link']} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-700 transition-colors">
              <ExternalLink size={10} />
              Product
            </a>
          )}
          {product['Data Sheet link'] && (
            <a href={product['Data Sheet link']} target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-700 transition-colors">
              <ExternalLink size={10} />
              Datasheet
            </a>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
        {/* <button onClick={() => onEdit(product.id)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 hover:text-blue-600 transition-all">
          <Edit2 size={12} />
          Edit
        </button>
        <button onClick={() => onKb(product.id)}
        </button> */}
        <button onClick={() => onView(product)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 hover:text-purple-600 transition-all">
          <BookOpen size={12} />
          View
        </button>
        <button onClick={() => onToggle(product)}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-all ${isActive
            ? 'text-gray-600 hover:bg-orange-50 hover:text-orange-500'
            : 'text-gray-600 hover:bg-green-50 hover:text-green-500'
            }`}>
          {isActive ? <PowerOff size={12} /> : <Power size={12} />}
          {isActive ? 'Off' : 'On'}
        </button>
        <button onClick={() => onDelete(product)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-red-50 hover:text-red-500 transition-all">
          <Trash2 size={12} />
          Del
        </button>
      </div>
    </motion.div>
  )
}

function ProductRow({ product, onToggle, onDelete, onView }) {
  const isActive = product.status === 'Active'
  const hasScore = product.coverage_score !== null && product.coverage_score !== undefined
  const pct = hasScore ? Math.round(product.coverage_score * 100) : null
  const coverageColor = !hasScore ? '#9ca3af' : pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <motion.tr layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="table-row">
      <td className="py-3 px-4">
        <div className="flex items-center gap-1">

          {/* View */}
          <button
            onClick={() => onView(product)}
            className="p-1.5 rounded-lg hover:bg-purple-50 hover:text-purple-600 text-gray-400 transition-all"
            title="View"
          >
            <BookOpen size={13} />
          </button>

          {/* Toggle Active/Inactive */}
          <button
            onClick={() => onToggle(product)}
            className={`p-1.5 rounded-lg text-gray-400 transition-all ${isActive
              ? 'hover:bg-orange-50 hover:text-orange-500'
              : 'hover:bg-green-50 hover:text-green-500'
              }`}
            title={isActive ? 'Deactivate' : 'Activate'}
          >
            {isActive ? <PowerOff size={13} /> : <Power size={13} />}
          </button>

          {/* Delete */}
          <button
            onClick={() => onDelete(product)}
            className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 text-gray-400 transition-all"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>

        </div>
      </td>

      <td className="py-3 px-4 text-xs text-gray-500">{product.Brand || '—'}</td>
      <td className="py-3 px-4">
        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">
          {product.category || '—'}
        </span>
      </td>
      <td className="py-3 px-4 text-xs font-semibold text-gray-900">
        {product.price || product.singlePrice ? `₹${Number(product.price || product.singlePrice).toLocaleString()}` : '—'}
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-1.5">
          <div className="w-16 h-1 rounded-full bg-gray-100">
            <div className="h-full rounded-full" style={{ width: `${pct ?? 0}%`, background: coverageColor }} />
          </div>
          <span className="text-[10px] font-medium" style={{ color: coverageColor }}>
            {pct !== null ? `${pct}%` : '—'}
          </span>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-lg ${isActive ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-400'
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'}`} />
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </td>
      
      {/* Updated Actions Column */}
      <td className="py-3 px-4">
        <div className="flex items-center gap-1">

          {/* View */}
          <button
            onClick={() => onView(product)}
            className="p-1.5 rounded-lg hover:bg-purple-50 hover:text-purple-600 text-gray-400 transition-all"
            title="View"
          >
            <BookOpen size={13} />
          </button>

          {/* Toggle */}
          <button
            onClick={() => onToggle(product)}
            className={`p-1.5 rounded-lg text-gray-400 transition-all ${isActive
              ? 'hover:bg-orange-50 hover:text-orange-500'
              : 'hover:bg-green-50 hover:text-green-500'
              }`}
            title={isActive ? 'Deactivate' : 'Activate'}
          >
            {isActive ? <PowerOff size={13} /> : <Power size={13} />}
          </button>

          {/* Delete */}
          <button
            onClick={() => onDelete(product)}
            className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 text-gray-400 transition-all"
            title="Delete"
          >
            <Trash2 size={13} />
          </button>

        </div>
      </td>
    </motion.tr>
  )
}

const PAGE_SIZE = 12

export default function Products() {
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [viewMode, setViewMode] = useState('grid')
  const [page, setPage] = useState(1)

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState(null)

  const [detailOpen, setDetailOpen] = useState(false)
  const [detailProduct, setDetailProduct] = useState(null)

  const fetchProducts = () => {
    setLoading(true)
    ShowAllProductService(null,
      (data) => {
        const mapped = (data || []).map(p => ({
          ...p,
          name: p.Product_id || p.name || 'Unnamed Product',
          category: p.Category || p.category || 'Uncategorized',
          price: p.Price !== undefined ? p.Price : (p.single_price || p.singlePrice || 0),
          status: p.is_active !== undefined ? (p.is_active ? 'Active' : 'Inactive') : 'Active',
        }))
        setProducts(mapped)
        setLoading(false)
      },
      (_s, err) => { console.error(err); setLoading(false) }
    )
  }

  useEffect(() => { fetchProducts() }, [])

  const handleToggle = (product) => {
    ToggleActiveInactiveService(product.id,
      () => setProducts(prev => prev.map(p =>
        p.id === product.id ? { ...p, status: p.status === 'Active' ? 'Inactive' : 'Active' } : p
      )),
      (_s, err) => alert('Toggle failed: ' + err)
    )
  }

  const handleDelete = () => {
    if (!selectedProduct) return
    DeleteProductService(selectedProduct.id,
      () => { setProducts(prev => prev.filter(p => p.id !== selectedProduct.id)); setDeleteDialogOpen(false) },
      (_s, err) => alert('Delete failed: ' + err)
    )
  }

  const filtered = products.filter(p => {
    const matchSearch = p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p['Order Code'] || '').toLowerCase().includes(search.toLowerCase()) ||
      (p.Brand || '').toLowerCase().includes(search.toLowerCase())
    const matchCat = categoryFilter === 'All' || p.category === categoryFilter
    const matchStatus = statusFilter === 'All' || p.status === statusFilter
    return matchSearch && matchCat && matchStatus
  })

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const categories = ['All', ...new Set(products.map(p => p.category).filter(Boolean))]
  const active = products.filter(p => p.status === 'Active').length
  const scoredProducts = products.filter(p => p.coverage_score !== null && p.coverage_score !== undefined)
  const avgCoverage = scoredProducts.length
    ? Math.round(scoredProducts.reduce((a, p) => a + p.coverage_score * 100, 0) / scoredProducts.length)
    : 0

  const summaryCards = [
    { label: 'Total Products', value: products.length, color: 'text-primary-400' },
    { label: 'Active', value: active, color: 'text-accent-green' },
    { label: 'Inactive', value: products.length - active, color: 'text-gray-400' },
    { label: 'Avg Coverage', value: scoredProducts.length ? `${avgCoverage}%` : '—', color: scoredProducts.length ? (avgCoverage >= 70 ? 'text-accent-green' : avgCoverage >= 40 ? 'text-accent-orange' : 'text-accent-red') : 'text-gray-400' },
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

      {/* Controls */}
      <div className="glass-card p-4">
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div className="flex flex-col sm:flex-row gap-3 flex-1">
            <div className="relative flex-1 max-w-sm">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
                placeholder="Search name, order code, brand..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-blue-500 transition-all shadow-sm" />
            </div>
            <select value={categoryFilter} onChange={e => { setCategoryFilter(e.target.value); setPage(1) }}
              className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
              {categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              className="px-3 py-2 text-sm rounded-xl bg-gray-50 border border-gray-200 text-gray-900 focus:outline-none focus:border-blue-500 shadow-sm">
              {['All', 'Active', 'Inactive'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={fetchProducts}
              className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100 transition-all">
              <RefreshCw size={14} />
            </button>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* View toggle */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-gray-100">
              <button onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
                <LayoutGrid size={14} />
              </button>
              <button onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-lg transition-all ${viewMode === 'list' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}>
                <List size={14} />
              </button>
            </div>
            <Link to="/add-product"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-all shadow-sm">
              <Plus size={14} />
              Add Product
            </Link>
          </div>
        </div>

        <p className="text-xs text-gray-400 mt-3">
          Showing {filtered.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} products
        </p>
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-card p-12 flex justify-center text-gray-400 text-sm">Loading products...</div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-12 flex flex-col items-center gap-3 text-center">
          <Package size={32} className="text-gray-300" />
          <p className="text-sm text-gray-500">No products found.</p>
          <Link to="/add-product"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-all mt-1">
            <Plus size={14} />
            Add your first product
          </Link>
        </div>
      ) : viewMode === 'grid' ? (
        <AnimatePresence mode="popLayout">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {paginated.map((product, i) => (
              <motion.div key={product.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}>
                <ProductCard
                  product={product}
                  onEdit={(id) => navigate(`/edit-product/${id}`)}

                  onKb={(id) => {
                    const product = paginated.find((p) => p.id === id)
                    setDetailProduct(product)
                    setDetailOpen(true)
                  }}

                  onToggle={handleToggle}

                  onDelete={(p) => {
                    setSelectedProduct(p)
                    setDeleteDialogOpen(true)
                  }}

                  onView={(p) => {
                    setDetailProduct(p)
                    setDetailOpen(true)
                  }}
                />
              </motion.div>
            ))}
          </div>
        </AnimatePresence>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[800px]">
              <thead>
                <tr className="border-b border-gray-200">
                  {['Product', 'Brand', 'Category', 'Price', 'Coverage', 'Status', 'Actions'].map(h => (
                    <th key={h} className="text-left py-3 px-4 text-gray-500 font-medium uppercase tracking-wider text-[10px]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginated.map((product) => (
                  <ProductRow key={product.id} product={product}
                    onEdit={(id) => navigate(`/edit-product/${id}`)}
                    onToggle={handleToggle}
                    onDelete={(p) => { setSelectedProduct(p); setDeleteDialogOpen(true) }}
                    onView={(p) => { setDetailProduct(p); setDetailOpen(true) }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
            <ChevronLeft size={14} />
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => setPage(p)}
              className={`w-7 h-7 rounded-lg text-xs font-medium transition-all ${p === page ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'
                }`}>
              {p}
            </button>
          ))}
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed text-gray-500 transition-all">
            <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Product Detail Modal */}
      <AnimatePresence>
        {detailOpen && detailProduct && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/30 backdrop-blur-sm"
              onClick={() => setDetailOpen(false)} />
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto p-6 z-10">
              <div className="flex items-start justify-between mb-5">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">{detailProduct.name}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">{detailProduct['Order Code']} · {detailProduct.Brand}</p>
                </div>
                <button onClick={() => setDetailOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-all">
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-4 text-sm">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 rounded-xl bg-gray-50">
                    <p className="text-[10px] text-gray-400 mb-1">Category</p>
                    <p className="text-xs font-semibold text-gray-800">{detailProduct.category}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50">
                    <p className="text-[10px] text-gray-400 mb-1">Sub-category</p>
                    <p className="text-xs font-semibold text-gray-800">{detailProduct['Sub-category'] || '—'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50">
                    <p className="text-[10px] text-gray-400 mb-1">Single Price</p>
                    <p className="text-sm font-bold text-blue-600">
                      {detailProduct.price ? `₹${Number(detailProduct.price).toLocaleString()}` : '—'}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50">
                    <p className="text-[10px] text-gray-400 mb-1">Bulk Price</p>
                    <p className="text-sm font-bold text-gray-700">
                      {detailProduct.bulk_price ? `₹${Number(detailProduct.bulk_price).toLocaleString()}` : '—'}
                    </p>
                  </div>
                </div>

                <CoverageBar score={detailProduct.coverage_score} />

                {detailProduct.sections?.description && (
                  <div>
                    <p className="text-[10px] text-gray-400 mb-1.5">Description</p>
                    <p className="text-xs text-gray-600 leading-relaxed">{detailProduct.sections.description}</p>
                  </div>
                )}

                {detailProduct.sections?.features?.length > 0 && (
                  <div>
                    <p className="text-[10px] text-gray-400 mb-2">Features</p>
                    <ul className="space-y-1">
                      {detailProduct.sections.features.map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                          <span className="w-1 h-1 rounded-full bg-blue-400 mt-1.5 flex-shrink-0" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(detailProduct['Product Link'] || detailProduct['Data Sheet link'] || detailProduct['User Manual'] || detailProduct['Learning Center SDK']) && (
                  <div>
                    <p className="text-[10px] text-gray-400 mb-2">Resources</p>
                    <div className="flex flex-wrap gap-2">
                      {[
                        ['Product Page', detailProduct['Product Link']],
                        ['Data Sheet', detailProduct['Data Sheet link']],
                        ['User Manual', detailProduct['User Manual']],
                        ['SDK', detailProduct['Learning Center SDK']],
                      ].filter(([, url]) => url).map(([label, url]) => (
                        <a key={label} href={url} target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-blue-50 text-blue-600 text-xs font-medium hover:bg-blue-100 transition-all">
                          <ExternalLink size={10} />
                          {label}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex gap-2 mt-6 pt-4 border-t border-gray-100">
                <button onClick={() => { navigate(`/edit-product/${detailProduct.id}`); setDetailOpen(false) }}
                  className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl bg-blue-50 text-blue-600 text-sm font-medium hover:bg-blue-100 transition-all">
                  <Edit2 size={13} />
                  Edit
                </button>
                <button onClick={() => { navigate(`/knowledge-base/${detailProduct.id}`); setDetailOpen(false) }}
                  className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl bg-purple-50 text-purple-600 text-sm font-medium hover:bg-purple-100 transition-all">
                  <BookOpen size={13} />
                  Knowledge Base
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Delete Confirm */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}
        PaperProps={{ sx: { borderRadius: 3 } }}>
        <DialogTitle sx={{ fontWeight: 700 }}>Delete Product</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete <strong>{selectedProduct?.name}</strong>? This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteDialogOpen(false)} color="inherit">Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">Delete</Button>
        </DialogActions>
      </Dialog>

    </motion.div>
  )
}

import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  Database,
  Edit2,
  HelpCircle,
  Plus,
  Save, Trash2, X
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  AddProductKnowledgeService,
  DeleteProductChunkService,
  GetProductEmbeddingsService,
  GetProductKnowledgeService,
  ShowOneProductService,
  UpdateProductChunkService,
  UpdateProductKnowledgeService,
} from '../services/ApiService'

const CATEGORIES = ['description', 'features', 'specification', 'product_knowledge', 'general']

function EntryDialog({ open, entry, productId, onClose, onSaved }) {
  const isEdit = Boolean(entry)
  const [category, setCategory] = useState(entry?.category || 'general')
  const [content, setContent] = useState(entry?.content || '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setCategory(entry?.category || 'general')
      setContent(entry?.content || '')
    }
  }, [open, entry])

  const handleSave = () => {
    if (!content.trim()) return
    setSaving(true)
    const payload = { category, content }
    const svc = isEdit
      ? (ok, err) => UpdateProductKnowledgeService(productId, entry.id, payload, ok, err)
      : (ok, err) => AddProductKnowledgeService(productId, payload, ok, err)
    svc(
      () => { setSaving(false); onSaved() },
      (_s, err) => { setSaving(false); alert('Save failed: ' + err) }
    )
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.96, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }} transition={{ type: 'spring', damping: 28 }}
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg z-10 overflow-hidden">

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-900">
            {isEdit ? 'Edit Knowledge Entry' : 'Add Knowledge Entry'}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
            <X size={15} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">Chunk Type / Category</label>
            <div className="flex flex-col gap-3">
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    // Just pressing enter keeps the value
                  }
                }}
                placeholder="Type a custom chunk type (e.g. troubleshooting) or select below..."
                className="w-full text-sm text-gray-700 border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400 transition-all"
              />
              <div className="flex gap-2 flex-wrap">
                {CATEGORIES.map(c => (
                  <button key={c} onClick={(e) => { e.preventDefault(); setCategory(c); }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border
                      ${category === c
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-blue-300'}`}>
                    {c}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">
              Content <span className="text-red-400">*</span>
            </label>
            <textarea value={content} onChange={e => setContent(e.target.value)} rows={7}
              placeholder={
                category === 'warranty' ? 'e.g. This product comes with a 1-year replacement warranty. Contact support@rdltech.in for claims.' :
                  category === 'pricing' ? 'e.g. Bulk orders of 10+ units get 15% discount. Contact sales for OEM pricing.' :
                    category === 'compatibility' ? 'e.g. Compatible with Arduino, Raspberry Pi, and ESP32 via UART/I2C.' :
                      category === 'technical' ? 'e.g. Operating voltage: 5V DC. Max current draw: 500mA. Temperature range: -20°C to 85°C.' :
                        'Enter detailed product knowledge that the AI should use to answer customer questions...'
              }
              className="w-full text-sm text-gray-700 border border-gray-200 rounded-xl px-4 py-3 resize-none focus:outline-none focus:border-blue-400 transition-all leading-relaxed" />
            <p className="text-[10px] text-gray-400 mt-1">{content.length} chars · This text will be embedded into the RAG vector store immediately on save.</p>
          </div>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/60">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button onClick={handleSave} disabled={!content.trim() || saving}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all disabled:opacity-50">
            <Save size={13} />
            {saving ? 'Saving...' : isEdit ? 'Update Entry' : 'Save & Embed'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

function ChunkEditDialog({ open, chunk, productId, onClose, onSaved }) {
  const [content, setContent] = useState(chunk?.document || '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) setContent(chunk?.document || '')
  }, [open, chunk])

  const handleSave = () => {
    if (!content.trim()) return
    setSaving(true)
    UpdateProductChunkService(productId, chunk.chunk_id, { content },
      () => { setSaving(false); onSaved(content) },
      (_s, err) => { setSaving(false); alert('Save failed: ' + err) }
    )
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <motion.div initial={{ opacity: 0, scale: 0.96, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96 }} transition={{ type: 'spring', damping: 28 }}
        className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg z-10 overflow-hidden">

        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-900">
            Edit Chunk {chunk?.chunk_type ? `— ${chunk.chunk_type.replace(/_/g, ' ')}` : ''}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
            <X size={15} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">
              Chunk Text <span className="text-red-400">*</span>
            </label>
            <textarea value={content} onChange={e => setContent(e.target.value)} rows={9}
              className="w-full text-sm text-gray-700 border border-gray-200 rounded-xl px-4 py-3 resize-none focus:outline-none focus:border-blue-400 transition-all leading-relaxed font-mono" />
            <p className="text-[10px] text-gray-400 mt-1">{content.length} chars · Re-embedded into the RAG vector store immediately on save.</p>
          </div>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 bg-gray-50/60">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button onClick={handleSave} disabled={!content.trim() || saving}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all disabled:opacity-50">
            <Save size={13} />
            {saving ? 'Saving...' : 'Update Chunk'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}

const CHUNK_COLORS = {
  description: 'bg-blue-50 text-blue-700',
  features: 'bg-emerald-50 text-emerald-700',
  specification: 'bg-purple-50 text-purple-700',
  specifications: 'bg-purple-50 text-purple-700',
  package_contains: 'bg-amber-50 text-amber-700',
  package_includes: 'bg-amber-50 text-amber-700',
  frequently_bought_together: 'bg-pink-50 text-pink-700',
  product_knowledge: 'bg-indigo-50 text-indigo-700',
}

function ChunkTableRow({ chunk, index, onEdit, onDelete }) {
  const color = CHUNK_COLORS[chunk.chunk_type] || 'bg-gray-50 text-gray-600'
  return (
    <tr className="hover:bg-gray-50/50 transition-colors group">
      <td className="px-4 py-4 text-xs font-medium text-gray-500 text-center align-top w-16">
        {index}
      </td>
      <td className="px-4 py-4 align-top w-48">
        <span className={`text-[10px] font-semibold px-2.5 py-1 rounded-full ${color} inline-block whitespace-nowrap`}>
          {chunk.chunk_type.replace(/_/g, ' ')}
        </span>
      </td>
      <td className="px-4 py-4">
        <div className="text-[11px] text-gray-700 leading-relaxed whitespace-pre-wrap font-mono bg-gray-50/50 p-3 rounded-lg border border-gray-100 max-h-48 overflow-y-auto">
          {chunk.document}
        </div>
      </td>
      <td className="px-4 py-4 align-top w-32">
        <div className="flex items-center justify-center gap-1">
          <button onClick={() => onEdit?.(chunk)}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-blue-50 hover:text-blue-600 transition-all">
            <Edit2 size={16} />
          </button>
          <button onClick={() => onDelete?.(chunk)}
            className="p-1.5 rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600 transition-all">
            <Trash2 size={16} />
          </button>
        </div>
      </td>
    </tr>
  )
}

export default function KnowledgeBase() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [entries, setEntries] = useState([])
  const [chunks, setChunks] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingEntry, setEditingEntry] = useState(null)
  const [chunkDialogOpen, setChunkDialogOpen] = useState(false)
  const [editingChunk, setEditingChunk] = useState(null)

  const fetchAll = () => {
    setLoading(true)
    ShowOneProductService({ id },
      (pdata) => {
        setProduct(pdata)
        GetProductKnowledgeService(id,
          (kdata) => {
            setEntries(kdata?.items || [])
            GetProductEmbeddingsService(id,
              (edata) => { setChunks(edata?.chunks || []); setLoading(false) },
              () => setLoading(false)
            )
          },
          () => setLoading(false)
        )
      },
      () => setLoading(false)
    )
  }

  // fetchAll is redefined every render (not memoized) — including it here would
  // re-run this on every render instead of only when the product id changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchAll() }, [id])

  const handleEditChunk = (chunk) => {
    setEditingChunk(chunk)
    setChunkDialogOpen(true)
  }

  const onChunkSaved = (newContent) => {
    setChunks(prev => prev.map(c => c.chunk_id === editingChunk.chunk_id ? { ...c, document: newContent } : c))
    setChunkDialogOpen(false)
  }

  const handleDeleteChunk = (chunk) => {
    if (!window.confirm(`Delete this chunk?\n\n"${(chunk.document || '').slice(0, 80)}..."`)) return
    DeleteProductChunkService(id, chunk.chunk_id,
      () => setChunks(prev => prev.filter(c => c.chunk_id !== chunk.chunk_id)),
      (_s, err) => alert('Delete failed: ' + err)
    )
  }

  const openAdd = () => { setEditingEntry(null); setDialogOpen(true) }
  const onSaved = () => { setDialogOpen(false); fetchAll() }

  if (loading && !product) {
    return <div className="flex justify-center py-20 text-gray-400 text-sm">Loading...</div>
  }

  if (!product) {
    return (
      <div className="flex flex-col items-center py-20 gap-3">
        <p className="text-sm text-gray-500">Product not found.</p>
        <button onClick={() => navigate('/products')} className="text-blue-600 text-sm underline">Back to Products</button>
      </div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/products')}
            className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-500 hover:bg-gray-100 transition-all">
            <ArrowLeft size={15} />
          </button>
          <div>
            <h1 className="text-lg font-bold text-gray-900">{product.Product_id || product.name}</h1>
            <p className="text-xs text-gray-400">
              {product['Order Code'] || product.order_code} · {entries.length} knowledge entr{entries.length !== 1 ? 'ies' : 'y'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchAll}
            className="p-2 rounded-xl bg-gray-50 border border-gray-200 text-gray-400 hover:bg-gray-100 transition-all">
            {/* <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> */}
          </button>
          <button onClick={openAdd}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all">
            <Plus size={14} />
            Add Chunks  
          </button>
        </div>
      </div>

      {/* Product meta card */}
      <div className="glass-card p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        {[
          { label: 'Category', value: product.Category || product.category || '—' },
          { label: 'Brand', value: product.Brand || product.brand || '—' },
          { label: 'Single Price', value: product.Price ? `₹${Number(product.Price).toLocaleString()}` : '—' },
          { label: 'Bulk Price', value: product.bulk_price ? `₹${Number(product.bulk_price).toLocaleString()}` : '—' },
        ].map((f, i) => (
          <div key={i}>
            <p className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">{f.label}</p>
            <p className="font-semibold text-gray-800">{f.value}</p>
          </div>
        ))}
      </div>

      {/* Product FAQs — separate table from the RAG chunks */}
      {Array.isArray(product.faqs) && product.faqs.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <HelpCircle size={14} className="text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-700">
              Frequently Asked Questions
            </h2>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
              {product.faqs.length} FAQ{product.faqs.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-50/50 border-b border-gray-100 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                    <th className="px-4 py-3 w-16 text-center">Sl No.</th>
                    <th className="px-4 py-3 w-1/3">Question</th>
                    <th className="px-4 py-3">Answer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {product.faqs.map((faq, index) => (
                    <tr key={index} className="hover:bg-gray-50/50 transition-colors align-top">
                      <td className="px-4 py-4 text-xs font-medium text-gray-500 text-center w-16">
                        {index + 1}
                      </td>
                      <td className="px-4 py-4 w-1/3">
                        <p className="text-xs font-semibold text-gray-800 leading-relaxed">{faq.question}</p>
                      </td>
                      <td className="px-4 py-4">
                        <p className="text-[11px] text-gray-600 leading-relaxed whitespace-pre-wrap">{faq.answer}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!loading && chunks.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <Database size={14} className="text-gray-400" />
            <h2 className="text-sm font-semibold text-gray-700">
              RAG Chunks in Vector Store
            </h2>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
              {chunks.length} chunks
            </span>
          </div>

          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-50/50 border-b border-gray-100 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
                    <th className="px-4 py-3 w-16 text-center">Sl No.</th>
                    <th className="px-4 py-3 w-48">Chunk Type</th>
                    <th className="px-4 py-3">Chunk Description</th>
                    <th className="px-4 py-3 w-32 text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {chunks.map((chunk, index) => (
                    <ChunkTableRow
                      key={chunk.chunk_id}
                      chunk={chunk}
                      index={index + 1}
                      onEdit={handleEditChunk}
                      onDelete={handleDeleteChunk}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {!loading && chunks.length === 0 && (
        <div className="glass-card p-5 flex items-center gap-3 border border-amber-200 bg-amber-50/40">
          <Database size={16} className="text-amber-500 flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold text-amber-700">No RAG chunks found</p>
            <p className="text-[10px] text-amber-600 mt-0.5">
              This product has not been ingested into the vector store yet. Run the data ingestion script or add knowledge entries above to embed content.
            </p>
          </div>
        </div>
      )}

      <AnimatePresence>
        {dialogOpen && (
          <EntryDialog
            open={dialogOpen}
            entry={editingEntry}
            productId={id}
            onClose={() => setDialogOpen(false)}
            onSaved={onSaved}
          />
        )}
        {chunkDialogOpen && (
          <ChunkEditDialog
            open={chunkDialogOpen}
            chunk={editingChunk}
            productId={id}
            onClose={() => setChunkDialogOpen(false)}
            onSaved={onChunkSaved}
          />
        )}
      </AnimatePresence>

    </motion.div>
  )
}

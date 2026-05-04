import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Plus, Edit2, Trash2, RefreshCw, BookOpen,
  Tag, Save, X, Database, ChevronDown, ChevronRight
} from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ShowOneProductService,
  GetProductKnowledgeService,
  AddProductKnowledgeService,
  UpdateProductKnowledgeService,
  DeleteProductKnowledgeService,
  GetProductEmbeddingsService,
} from '../services/ApiService'

const CATEGORIES = ['general', 'warranty', 'pricing', 'compatibility', 'technical']

const CAT_COLOR = {
  general:       'bg-gray-100 text-gray-600',
  warranty:      'bg-blue-50 text-blue-700',
  pricing:       'bg-emerald-50 text-emerald-700',
  compatibility: 'bg-purple-50 text-purple-700',
  technical:     'bg-amber-50 text-amber-700',
}

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
            <label className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide mb-1.5 block">Category</label>
            <div className="flex gap-2 flex-wrap">
              {CATEGORIES.map(c => (
                <button key={c} onClick={() => setCategory(c)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border
                    ${category === c
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-gray-50 text-gray-600 border-gray-200 hover:border-blue-300'}`}>
                  {c}
                </button>
              ))}
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

const CHUNK_COLORS = {
  description:        'bg-blue-50 text-blue-700',
  features:           'bg-emerald-50 text-emerald-700',
  specification:      'bg-purple-50 text-purple-700',
  specifications:     'bg-purple-50 text-purple-700',
  package_contains:   'bg-amber-50 text-amber-700',
  package_includes:   'bg-amber-50 text-amber-700',
  frequently_bought_together: 'bg-pink-50 text-pink-700',
  product_knowledge:  'bg-indigo-50 text-indigo-700',
}

function ChunkRow({ chunk }) {
  const [open, setOpen] = useState(false)
  const color = CHUNK_COLORS[chunk.chunk_type] || 'bg-gray-50 text-gray-600'
  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition-all text-left group">
        <span className={`text-[9px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${color}`}>
          {chunk.chunk_type.replace(/_/g, ' ')}
        </span>
        <span className="text-[10px] text-gray-500 truncate flex-1">
          {(chunk.document || '').slice(0, 120)}
        </span>
        {open
          ? <ChevronDown size={12} className="text-gray-400 flex-shrink-0" />
          : <ChevronRight size={12} className="text-gray-400 flex-shrink-0 opacity-0 group-hover:opacity-100" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }}
            exit={{ height: 0 }} className="overflow-hidden">
            <pre className="text-[10px] text-gray-700 bg-gray-50 border-t border-gray-100 px-4 py-3 whitespace-pre-wrap leading-relaxed font-mono max-h-56 overflow-y-auto">
              {chunk.document}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
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

  useEffect(() => { fetchAll() }, [id])

  const handleDelete = (entryId, content) => {
    if (!window.confirm(`Delete this entry?\n\n"${content.slice(0, 80)}..."`)) return
    DeleteProductKnowledgeService(id, entryId,
      () => setEntries(prev => prev.filter(e => e.id !== entryId)),
      (_s, err) => alert('Delete failed: ' + err)
    )
  }

  const openAdd = () => { setEditingEntry(null); setDialogOpen(true) }
  const openEdit = (entry) => { setEditingEntry(entry); setDialogOpen(true) }
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
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={openAdd}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all">
            <Plus size={14} />
            Add Knowledge
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

      {/* Entries */}
      {loading ? (
        <div className="glass-card p-10 text-center text-gray-400 text-sm">Loading entries...</div>
      ) : entries.length === 0 ? (
        <div className="glass-card p-12 flex flex-col items-center gap-3 text-center">
          <BookOpen size={28} className="text-gray-300" />
          <p className="text-sm text-gray-500">No knowledge entries yet.</p>
          <p className="text-xs text-gray-400 max-w-xs">Add warranty info, pricing details, compatibility notes, or technical specs so the AI can answer customer questions accurately.</p>
          <button onClick={openAdd}
            className="mt-2 flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all">
            <Plus size={14} />
            Add first entry
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {entries.map((entry, i) => (
              <motion.div key={entry.id}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96 }} transition={{ delay: i * 0.03 }}
                className="glass-card p-4 group">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <Tag size={14} className="text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${CAT_COLOR[entry.category] || CAT_COLOR.general}`}>
                          {entry.category}
                        </span>
                        {entry.added_by && (
                          <span className="text-[9px] text-gray-400">by {entry.added_by}</span>
                        )}
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{entry.content}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openEdit(entry)}
                      className="p-1.5 rounded-lg hover:bg-blue-50 hover:text-blue-600 text-gray-400 transition-all">
                      <Edit2 size={13} />
                    </button>
                    <button onClick={() => handleDelete(entry.id, entry.content)}
                      className="p-1.5 rounded-lg hover:bg-red-50 hover:text-red-500 text-gray-400 transition-all">
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* RAG Embedding Chunks */}
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
            <p className="text-[10px] text-gray-400 ml-1">
              Click any chunk to read the full embedded text
            </p>
          </div>
          <div className="space-y-1.5">
            {chunks.map(chunk => <ChunkRow key={chunk.chunk_id} chunk={chunk} />)}
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
      </AnimatePresence>

    </motion.div>
  )
}

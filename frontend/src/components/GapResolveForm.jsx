/**
 * GapResolveForm — shared gap resolution form used in Gmail Inbox and Knowledge Gaps page.
 *
 * Props:
 *   gap          — gap object  { question, topic, product_name, product_id }
 *   onResolve    — (answer, category, productId) => void  — called when user submits
 *   onCancel     — () => void
 *   loading      — bool
 */
import { useEffect, useState } from 'react'
import ApplicationStore from '../utils/ApplicationStore'

// Direct fetch so we can send query params — _fetchService ignores GET body
function fetchProducts(callback) {
  const { accessToken } = ApplicationStore().getStorage('userDetails') || {}
  const base = import.meta.env.VITE_API_URL
  fetch(`${base}products/?limit=200&is_active=true`, {
    headers: {
      'Content-Type': 'application/json',
      authorization: `Bearer ${accessToken}`,
    },
    credentials: 'same-origin',
  })
    .then(r => r.json())
    .then(data => {
      // endpoint returns plain array
      callback(Array.isArray(data) ? data : (data?.items || []))
    })
    .catch(() => callback([]))
}

const PRESET_CATEGORIES = [
  { value: 'warranty',      label: 'Warranty' },
  { value: 'pricing',       label: 'Pricing' },
  { value: 'compatibility', label: 'Compatibility' },
  { value: 'availability',  label: 'Availability' },
  { value: 'technical',     label: 'Technical' },
  { value: 'general',       label: 'General' },
  { value: '__other__',     label: '+ New category…' },
]

export default function GapResolveForm({ gap, onResolve, onCancel, loading = false }) {
  const [products, setProducts]         = useState([])
  const [productId, setProductId]       = useState(gap?.product_id || '')
  const [category, setCategory]         = useState(gap?.topic || 'general')
  const [customCategory, setCustomCategory] = useState('')
  const [answer, setAnswer]             = useState('')

  useEffect(() => {
    fetchProducts(setProducts)
  }, [])

  // Sync when gap changes (different gap opened)
  useEffect(() => {
    setProductId(gap?.product_id || '')
    setCategory(gap?.topic || 'general')
    setCustomCategory('')
    setAnswer('')
  }, [gap?.question, gap?.product_id, gap?.topic])

  const effectiveCategory = category === '__other__' ? customCategory.trim() : category
  const canSubmit = answer.trim() && effectiveCategory && (category !== '__other__' || customCategory.trim())

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSubmit) return
    onResolve(answer.trim(), effectiveCategory, productId || null)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Question being answered */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2.5">
        <p className="text-[10px] font-semibold text-amber-600 uppercase tracking-wide mb-0.5">Question from customer</p>
        <p className="text-xs text-amber-800 font-medium">{gap?.question || '—'}</p>
      </div>

      {/* Product selector */}
      <div>
        <label className="block text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Product
        </label>
        <select
          value={productId}
          onChange={e => setProductId(e.target.value)}
          className="w-full text-xs border border-gray-200 rounded-xl px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-indigo-400 transition-all">
          <option value="">— No specific product —</option>
          {products.map(p => {
            // Product API returns aliased fields: "Product_id" for name, "Order Code" for code
            const displayName = p['Product_id'] || p.name || 'Unnamed'
            const code = p['Order Code'] || p.order_code
            return (
              <option key={p.id} value={p.id}>
                {displayName}{code ? ` (${code})` : ''}
              </option>
            )
          })}
        </select>
        {gap?.product_name && !productId && (
          <p className="text-[10px] text-amber-500 mt-0.5">
            Suggested: <span className="font-medium">{gap.product_name}</span> — select from list above to link
          </p>
        )}
      </div>

      {/* Category selector */}
      <div>
        <label className="block text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Knowledge Category
        </label>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="w-full text-xs border border-gray-200 rounded-xl px-3 py-2 bg-white text-gray-700 focus:outline-none focus:border-indigo-400 transition-all">
          {PRESET_CATEGORIES.map(c => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        {category === '__other__' && (
          <input
            type="text"
            value={customCategory}
            onChange={e => setCustomCategory(e.target.value)}
            placeholder="Enter new category name…"
            className="mt-1.5 w-full text-xs border border-indigo-300 rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 transition-all"
            autoFocus
          />
        )}
        <p className="text-[10px] text-gray-400 mt-0.5">
          This answer will be stored under the selected category in the RAG knowledge base.
        </p>
      </div>

      {/* Answer */}
      <div>
        <label className="block text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Answer / Data to add
        </label>
        <textarea
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          rows={4}
          placeholder="Type the complete answer to embed into the knowledge base. Future emails about this topic will use this answer."
          className="w-full text-xs border border-gray-200 rounded-xl px-3 py-2.5 resize-none focus:outline-none focus:border-indigo-400 transition-all"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 pt-1">
        {onCancel && (
          <button type="button" onClick={onCancel}
            className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 transition-all">
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={!canSubmit || loading}
          className="px-4 py-1.5 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition-all disabled:opacity-50">
          {loading ? 'Saving…' : 'Save to Knowledge Base'}
        </button>
      </div>
    </form>
  )
}

import { motion } from 'framer-motion'
import { Package, Search, Plus, MoreHorizontal } from 'lucide-react'

// Placeholder data
const products = [
  { id: 'PRD-001', name: 'AI Voice Caller Starter', category: 'Software', status: 'Active', price: '$49/mo', sales: 124 },
  { id: 'PRD-002', name: 'Lead Gen Pro', category: 'Software', status: 'Active', price: '$99/mo', sales: 86 },
  { id: 'PRD-003', name: 'Enterprise Bundle', category: 'Services', status: 'Draft', price: '$499/mo', sales: 0 },
  { id: 'PRD-004', name: 'Custom Voice Cloning', category: 'Add-on', status: 'Active', price: '$29/mo', sales: 215 },
]

export default function Products() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Products</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your software products and Add-ons</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <Plus size={16} />
          Add Product
        </button>
      </div>

      <div className="glass-card">
        <div className="p-4 border-b border-gray-200 flex flex-col sm:flex-row gap-4 items-center justify-between">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input 
              type="text" 
              placeholder="Search products..." 
              className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all text-gray-900"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select className="bg-gray-50 border border-gray-200 text-gray-700 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2 w-full sm:w-auto">
              <option>All Categories</option>
              <option>Software</option>
              <option>Services</option>
              <option>Add-on</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/50">
                <th className="p-4 text-xs font-semibold text-gray-500">Product Name</th>
                <th className="p-4 text-xs font-semibold text-gray-500">Category</th>
                <th className="p-4 text-xs font-semibold text-gray-500">Price</th>
                <th className="p-4 text-xs font-semibold text-gray-500">Sales</th>
                <th className="p-4 text-xs font-semibold text-gray-500">Status</th>
                <th className="p-4 text-xs font-semibold text-gray-500 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} className="table-row">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center">
                        <Package size={18} className="text-blue-600" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{p.name}</p>
                        <p className="text-xs text-gray-500">{p.id}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className="text-sm text-gray-600">{p.category}</span>
                  </td>
                  <td className="p-4"><span className="text-sm font-medium text-gray-900">{p.price}</span></td>
                  <td className="p-4"><span className="text-sm text-gray-600">{p.sales}</span></td>
                  <td className="p-4">
                    <span className={`badge ${p.status === 'Active' ? 'badge-green' : 'badge-orange'}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <button className="p-2 text-gray-400 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
                      <MoreHorizontal size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}

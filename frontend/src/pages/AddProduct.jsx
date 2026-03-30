import { motion } from 'framer-motion'
import { Save, Image as ImageIcon } from 'lucide-react'

export default function AddProduct() {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Add New Product</h1>
        <p className="text-sm text-gray-500 mt-1">Create a new product or add-on for your platform</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card p-6 space-y-5">
            <h2 className="text-lg font-semibold text-gray-900 border-b border-gray-100 pb-3">Basic Information</h2>
            
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Product Name</label>
              <input type="text" className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" placeholder="e.g. Enterprise Voice AI" />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Description</label>
              <textarea rows={4} className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none" placeholder="Describe your product..."></textarea>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Category</label>
                <select className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all">
                  <option>Software</option>
                  <option>Services</option>
                  <option>Add-on</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Monthly Price ($)</label>
                <input type="number" className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all" placeholder="0.00" />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="glass-card p-6 space-y-5">
            <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">Product Image</h2>
            <div className="w-full h-40 border-2 border-dashed border-gray-200 rounded-xl flex flex-col items-center justify-center text-gray-400 bg-gray-50 hover:bg-gray-100 hover:border-gray-300 transition-colors cursor-pointer">
              <ImageIcon size={32} className="mb-2" />
              <span className="text-xs font-medium">Click to upload</span>
              <span className="text-[10px] mt-1">PNG, JPG up to 5MB</span>
            </div>
          </div>

          <div className="glass-card p-6 space-y-5">
            <h2 className="text-sm font-semibold text-gray-900 border-b border-gray-100 pb-3">Status</h2>
            <select className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:border-blue-500 transition-all">
              <option>Draft</option>
              <option>Active</option>
              <option>Archived</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4">
        <button className="btn-ghost">Cancel</button>
        <button className="btn-primary flex items-center gap-2">
          <Save size={16} />
          Save Product
        </button>
      </div>
    </motion.div>
  )
}
